"""
Industrial instruction rules + severity overrides + equipment parsing.

Deterministic only — no LLM calls.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.schemas.review import Severity

# Explicit rules for high-impact Rockwell instructions
INSTRUCTION_RULES: dict[str, str] = {
    "AFI": (
        "AFI always evaluates false. If an AFI is added before an output instruction, "
        "the downstream output path is disabled. Adding AFI on a failover request "
        "disables automatic standby equipment start."
    ),
    "XIC": (
        "XIC is true when its Boolean tag is true. Removing an XIC may remove a "
        "permissive or interlock condition. Adding an XIC adds another required condition."
    ),
    "XIO": (
        "XIO is true when its Boolean tag is false. Removing or adding an XIO can change "
        "fault, permissive, interlock, or leak/fire protection behavior."
    ),
    "OTE": (
        "OTE writes the result of the rung to a Boolean tag. The associated tag is usually "
        "the commanded result of that rung."
    ),
    "TON": (
        "TON is a non-retentive timer. A change to its preset changes the required delay."
    ),
    "MOV": (
        "MOV copies a value into another tag. A changed source value may represent a "
        "setpoint, limit, or configuration change."
    ),
    "ONS": (
        "ONS is a one-shot. Changes can alter pulse timing of commands or alarms."
    ),
}

DEFAULT_RULE = "Instruction behavior requires controls-engineering review."

# Severity keyword banks (lowercase)
_CRITICAL_KW = (
    "shutdown",
    "trip",
    "interlock",
    "emergency",
    "failover",
    "standby",
    "protection",
    "epo",
    "esd",
    "afi",
    "bypass",
    "disable",
    "safety",
    "fire",
    "leak",
)
_HIGH_KW = (
    "permissive",
    "sequence",
    "alarm",
    "limit",
    "auto recovery",
    "autorecovery",
    "handcmd",
    "mode",
    "start",
    "stop",
)
_MEDIUM_KW = (
    "timer",
    "ton",
    "setpoint",
    "sp",
    "delay",
    "indication",
    "hmi",
    "workflow",
    "preset",
)
_LOW_KW = (
    "comment",
    "documentation",
    "description",
    "format",
    "cosmetic",
    "alias",
)


def get_instruction_rule(instruction: str) -> str:
    """Return the industrial rule text for a single instruction mnemonic."""
    key = (instruction or "").strip().upper()
    base = "".join(ch for ch in key if ch.isalpha())
    return INSTRUCTION_RULES.get(base, DEFAULT_RULE)


def apply_rules(instructions: Iterable[str]) -> list[dict[str, str]]:
    """Map instruction mnemonics to rule records (deduped, order preserved)."""
    seen: set[str] = set()
    applied: list[dict[str, str]] = []
    for raw in instructions:
        instr = (raw or "").strip().upper()
        base = "".join(ch for ch in instr if ch.isalpha())
        if not base or base in seen:
            continue
        seen.add(base)
        applied.append({"instruction": base, "rule": get_instruction_rule(base)})
    return applied


def rules_for_change(
    instructions_added: list[str],
    instructions_removed: list[str],
) -> list[dict[str, str]]:
    """Rules for instructions that appear in either added or removed sets."""
    return apply_rules([*instructions_added, *instructions_removed])


def classify_severity(
    *,
    baseline_logic: str = "",
    revised_logic: str = "",
    instructions_added: list[str] | None = None,
    instructions_removed: list[str] | None = None,
    summary: str = "",
    tag_name: str = "",
    location: str = "",
) -> Severity:
    """
    Rule-based severity override (does not rely on LLM).

    CRITICAL: disables/bypasses shutdown, trip, interlock, emergency, failover (AFI),
              or equipment protection.
    HIGH: permissives, sequences, alarm actions, limits, auto recovery.
    MEDIUM: timing, noncritical setpoints, indication, operator workflow.
    LOW: documentation / low-impact configuration.
    """
    added = {i.upper() for i in (instructions_added or [])}
    removed = {i.upper() for i in (instructions_removed or [])}
    blob = " ".join(
        [
            baseline_logic or "",
            revised_logic or "",
            summary or "",
            tag_name or "",
            location or "",
            " ".join(added),
            " ".join(removed),
        ]
    ).lower()

    # Explicit CRITICAL patterns
    if "AFI" in added:
        return Severity.CRITICAL
    if any(k in blob for k in ("failover", "standby", "trip", "shutdown", "emergency", "epo")):
        if "AFI" in added or "removed" in blob or "xio" in removed or "xic" in removed:
            return Severity.CRITICAL
    if "leak" in blob and ("xio" in {r.lower() for r in removed} or "removed" in blob):
        return Severity.CRITICAL
    if any(k in blob for k in _CRITICAL_KW) and (
        "AFI" in added
        or any(x in removed for x in ("XIO", "XIC"))
        or "bypass" in blob
        or "disable" in blob
    ):
        return Severity.CRITICAL

    if any(k in blob for k in _HIGH_KW) or any(
        x in added or x in removed for x in ("XIC", "XIO", "OTE")
    ):
        # Permissive / interlock-ish without full critical signature
        if "permissive" in blob or "interlock" in blob or "alarm" in blob:
            return Severity.HIGH
        if any(k in blob for k in ("sequence", "mode", "handcmd", "start", "limit")):
            return Severity.HIGH

    if any(k in blob for k in _MEDIUM_KW) or "TON" in added or "TON" in removed or "MOV" in added:
        return Severity.MEDIUM

    if any(k in blob for k in _LOW_KW):
        return Severity.LOW

    return Severity.MEDIUM


def parse_equipment_roles(
    *,
    tag_name: str | None = None,
    equipment: str | None = None,
    baseline_logic: str = "",
    revised_logic: str = "",
    location: str = "",
    output_tags: list[str] | None = None,
    input_tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Separate trigger_equipment (device causing event) from affected_equipment
    (device affected by the logic change / output).
    """
    tags_in_logic = _extract_tags(f"{baseline_logic} {revised_logic}")
    out_tags = list(output_tags or [])
    in_tags = list(input_tags or [])

    # Heuristic: DI_/AI_/HMI_ inputs are triggers; CMD_/OTE targets are affected
    triggers: list[str] = []
    affected: list[str] = []

    for t in in_tags + tags_in_logic:
        if _is_trigger_tag(t) and t not in triggers:
            triggers.append(t)
    for t in out_tags + tags_in_logic:
        if _is_affected_tag(t) and t not in affected:
            affected.append(t)

    if equipment:
        # Named equipment is typically affected unless only a sensor context
        if equipment not in affected and equipment not in triggers:
            affected.insert(0, equipment)

    if tag_name:
        if _is_trigger_tag(tag_name) and tag_name not in triggers:
            triggers.insert(0, tag_name)
        elif tag_name not in affected:
            affected.insert(0, tag_name)

    if not triggers and tags_in_logic:
        triggers = [t for t in tags_in_logic if t not in affected][:3]
    if not affected and equipment:
        affected = [equipment]

    system = _infer_system(location, equipment, tag_name)
    routine, rung = _split_location(location)

    return {
        "trigger_equipment": triggers[:6],
        "affected_equipment": affected[:6],
        "affected_output": (out_tags[0] if out_tags else (tag_name or "")),
        "system": system,
        "routine": routine,
        "rung": rung,
    }


def _is_trigger_tag(tag: str) -> bool:
    u = tag.upper()
    return any(
        u.startswith(p)
        for p in ("DI_", "AI_", "HMI_", "ALM_", "FLT_", "XS_", "PS_", "LS_", "FS_")
    ) or "LEAK" in u or "FIRE" in u or "FAULT" in u


def _is_affected_tag(tag: str) -> bool:
    u = tag.upper()
    return any(
        u.startswith(p)
        for p in ("CMD_", "DO_", "AO_", "PERM", "FAILOVER", "RUN_", "START", "SPEED")
    ) or "PERMISSIVE" in u or "FAILOVER" in u or u.endswith("_CMD")


def _extract_tags(text: str) -> list[str]:
    # Rockwell-ish identifiers inside ladder text
    found = re.findall(r"\b[A-Za-z][A-Za-z0-9_]{2,}\b", text or "")
    skip = {
        "XIC",
        "XIO",
        "OTE",
        "OTL",
        "OTU",
        "TON",
        "TOF",
        "RTO",
        "MOV",
        "AFI",
        "ONS",
        "JSR",
        "RET",
        "TRUE",
        "FALSE",
    }
    out: list[str] = []
    seen: set[str] = set()
    for t in found:
        if t.upper() in skip:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _infer_system(
    location: str | None,
    equipment: str | None,
    tag_name: str | None,
) -> str:
    blob = f"{location or ''} {equipment or ''} {tag_name or ''}".upper()
    if "CHW" in blob or "CHWP" in blob:
        return "Chilled Water"
    if "AHU" in blob:
        return "Air Handling"
    if "CT" in blob or "COOLING" in blob:
        return "Cooling"
    return "Process"


def _split_location(location: str | None) -> tuple[str, str | None]:
    loc = location or ""
    m = re.search(r"rung\s*[:=]?\s*(\d+)", loc, re.I)
    rung = m.group(1) if m else None
    routine = re.split(r"/rung", loc, maxsplit=1, flags=re.I)[0].strip() or loc
    return routine, rung
