"""
Deterministic PLC change parser (no LLM).

Extracts structured facts for every changed rung / tag from baseline vs revised
L5X parse results. Used as the sole source of truth for downstream rules + LLM.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.change_models import BehavioralChange, DiffArtifactType, DiffReport
from app.schemas.findings import StructuredPlcChange
from app.services.name_normalizer import normalize_logic_text

# Rockwell-style instruction call: MNEMONIC(args)
_INSTR_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(([^)]*)\)")

# First argument is typically the primary tag / destination
_OUTPUT_INSTRUCTIONS = frozenset(
    {"OTE", "OTL", "OTU", "OSR", "OSF", "MOV", "COP", "CPS", "CLR", "CPT", "ADD", "SUB", "MUL", "DIV"}
)
_TIMER_INSTRUCTIONS = frozenset({"TON", "TOF", "RTO"})


def parse_instructions(logic_text: str | None) -> list[dict[str, str]]:
    """
    Parse ladder text into ordered instruction records.

    Each record: {mnemonic, args, raw}
    """
    if not logic_text:
        return []
    text = logic_text.strip()
    results: list[dict[str, str]] = []
    for match in _INSTR_RE.finditer(text):
        mnemonic = match.group(1).upper()
        args = match.group(2).strip()
        results.append(
            {
                "mnemonic": mnemonic,
                "args": args,
                "raw": f"{mnemonic}({args})",
            }
        )
    return results


def instruction_mnemonics(logic_text: str | None) -> list[str]:
    return [i["mnemonic"] for i in parse_instructions(logic_text)]


def extract_tags_from_logic(logic_text: str | None) -> tuple[list[str], list[str]]:
    """
    Heuristic split of tags into input_tags vs output_tags from instruction roles.
    """
    inputs: list[str] = []
    outputs: list[str] = []
    for instr in parse_instructions(logic_text):
        mnemonic = instr["mnemonic"]
        args = instr["args"]
        if not args:
            continue
        # First comma-separated token is usually the primary operand
        primary = args.split(",")[0].strip()
        # Drop array/member noise for listing; keep full token
        tag = primary.split(".")[0].strip() if primary else ""
        if not tag or re.fullmatch(r"-?\d+(\.\d+)?", tag):
            continue
        if mnemonic in _OUTPUT_INSTRUCTIONS or mnemonic in _TIMER_INSTRUCTIONS:
            # Timer: first arg is timer structure (output-ish); still list as output
            if tag not in outputs:
                outputs.append(tag)
            # Secondary operands on TON/MOV may be inputs (presets/tags)
            for extra in args.split(",")[1:]:
                t = extra.strip().split(".")[0]
                if t and not re.fullmatch(r"-?\d+(\.\d+)?", t) and t not in inputs and t not in outputs:
                    inputs.append(t)
        else:
            if tag not in inputs and tag not in outputs:
                inputs.append(tag)
    return inputs, outputs


def _location_parts(location: str) -> tuple[str, int | None]:
    """
    Parse locations like:
      P_DC_Cooling/R30_CHWP_Control/rung:5
      ControllerTag/CFG_CHW_DP_SP
    """
    loc = location or ""
    rung_match = re.search(r"rung:(\d+)", loc, re.IGNORECASE)
    rung_number = int(rung_match.group(1)) if rung_match else None
    # Routine is second path segment when program/routine/rung
    parts = [p for p in loc.split("/") if p]
    routine = parts[1] if len(parts) >= 2 and rung_number is not None else (
        parts[-1] if parts else loc
    )
    if routine.lower().startswith("rung:"):
        routine = parts[0] if parts else loc
    return routine, rung_number


def structured_change_from_behavioral(
    change: BehavioralChange,
) -> StructuredPlcChange:
    """
    Convert a BehavioralChange (diff engine) into strict structured PLC facts.
    No LLM.
    """
    baseline_logic = ""
    revised_logic = ""
    if change.artifact_type == DiffArtifactType.TAG:
        b = change.baseline or {}
        r = change.revised or {}
        name = change.tag_name or "TAG"
        baseline_logic = f"{name} = {b.get('value')!s}"
        revised_logic = f"{name} = {r.get('value')!s}"
        routine = f"ControllerTag/{name}"
        rung_number = None
        instructions_added: list[str] = []
        instructions_removed: list[str] = []
        # Treat tag value change as MOV-like configuration fact for rules
        if _norm_val(b.get("value")) != _norm_val(r.get("value")):
            instructions_added = ["MOV"]
        input_tags: list[str] = []
        output_tags = [name]
    else:
        b = change.baseline or {}
        r = change.revised or {}
        baseline_logic = str(b.get("text") or b.get("normalized_text") or "")
        revised_logic = str(r.get("text") or r.get("normalized_text") or "")
        routine, rung_number = _location_parts(change.location)
        base_set = set(instruction_mnemonics(baseline_logic))
        rev_set = set(instruction_mnemonics(revised_logic))
        instructions_added = sorted(rev_set - base_set)
        instructions_removed = sorted(base_set - rev_set)
        # Also detect argument-level changes for shared mnemonics (e.g. TON preset)
        if not instructions_added and not instructions_removed:
            if normalize_logic_text(baseline_logic) != normalize_logic_text(revised_logic):
                # Shared instructions whose args changed
                base_map = {i["mnemonic"]: i["raw"] for i in parse_instructions(baseline_logic)}
                rev_map = {i["mnemonic"]: i["raw"] for i in parse_instructions(revised_logic)}
                for m in sorted(set(base_map) & set(rev_map)):
                    if base_map[m] != rev_map[m]:
                        instructions_added.append(m)
        in_b, out_b = extract_tags_from_logic(baseline_logic)
        in_r, out_r = extract_tags_from_logic(revised_logic)
        input_tags = sorted(set(in_b) | set(in_r))
        output_tags = sorted(set(out_b) | set(out_r))
        if change.tag_name and change.tag_name not in output_tags:
            # keep explicit tag if present
            pass

    return StructuredPlcChange(
        routine=routine,
        rung_number=rung_number,
        baseline_logic=baseline_logic,
        revised_logic=revised_logic,
        instructions_added=instructions_added,
        instructions_removed=instructions_removed,
        output_tags=output_tags,
        input_tags=input_tags,
        location=change.location,
        change_id=change.change_id,
        equipment=change.equipment,
        tag_name=change.tag_name,
    )


def extract_structured_changes(diff_report: DiffReport) -> list[StructuredPlcChange]:
    """Extract structured PLC change facts for every behavioral change."""
    return [structured_change_from_behavioral(c) for c in diff_report.changes]


def _norm_val(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    try:
        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            num = float(text)
            if num.is_integer():
                return str(int(num))
            return str(num)
    except ValueError:
        pass
    return text
