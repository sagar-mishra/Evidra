"""
Deterministic L5X diff engine.

Compares baseline vs revised parsed projects and emits only true behavioral
differences (tag values/types and ladder logic). Export metadata and
whitespace-only formatting noise are ignored.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.schemas.change_models import (
    BehavioralChange,
    ChangeClass,
    DiffArtifactType,
    DiffOperation,
    DiffReport,
    DiffSummary,
)
from app.services.lxml_parser import L5XParseError, parse_l5x
from app.services.name_normalizer import (
    extract_equipment_from_tag,
    normalize_identity,
    normalize_logic_text,
    normalize_tag_name,
)

# Logical tag fields compared for behavioral equality.
_TAG_COMPARE_FIELDS: tuple[str, ...] = (
    "data_type",
    "tag_type",
    "constant",
    "value",
    "description",
)


class DiffEngineError(ValueError):
    """Raised when a diff cannot be produced from the given inputs."""


def diff_l5x_files(
    baseline_path: str | Path,
    revised_path: str | Path,
) -> DiffReport:
    """Parse two L5X files and return a behavioral DiffReport."""
    try:
        baseline = parse_l5x(baseline_path)
        revised = parse_l5x(revised_path)
    except L5XParseError as exc:
        raise DiffEngineError(str(exc)) from exc
    return diff_parsed_projects(baseline, revised)


def diff_parsed_projects(
    baseline: dict[str, Any],
    revised: dict[str, Any],
) -> DiffReport:
    """
    Diff two already-parsed L5X dictionaries (output of parse_l5x).

    Ignores metadata already stripped by the parser. Compares only logical
    tag fields and normalized ladder rung text.
    """
    if not isinstance(baseline, dict) or not isinstance(revised, dict):
        raise DiffEngineError("Baseline and revised must be parse_l5x result dicts")

    changes: list[BehavioralChange] = []
    changes.extend(_diff_tags(baseline.get("tags", {}), revised.get("tags", {})))
    changes.extend(
        _diff_programs(baseline.get("programs", {}), revised.get("programs", {}))
    )

    changes.sort(key=lambda c: (c.artifact_type.value, c.location, c.change_id))
    # Stable sequential IDs after sort
    for index, change in enumerate(changes, start=1):
        change.change_id = f"DIFF-{index:03d}"

    summary = _build_summary(changes)
    baseline_ctrl = (baseline.get("controller") or {}).get("name")
    revised_ctrl = (revised.get("controller") or {}).get("name")

    return DiffReport(
        baseline_source=str(baseline.get("source_file", "")),
        revised_source=str(revised.get("source_file", "")),
        baseline_controller=baseline_ctrl,
        revised_controller=revised_ctrl,
        changes=changes,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Tag diff
# ---------------------------------------------------------------------------


def _diff_tags(
    baseline_tags: dict[str, dict[str, Any]],
    revised_tags: dict[str, dict[str, Any]],
) -> list[BehavioralChange]:
    changes: list[BehavioralChange] = []
    all_names = sorted(set(baseline_tags) | set(revised_tags))

    for name in all_names:
        base = baseline_tags.get(name)
        rev = revised_tags.get(name)
        identity = normalize_identity(name)
        equipment = identity.equipment

        if base is None and rev is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.TAG,
                    operation=DiffOperation.ADDED,
                    change_class=_classify_tag(name, rev, None),
                    location=f"ControllerTag/{name}",
                    tag_name=name,
                    canonical_name=identity.canonical_name,
                    equipment=equipment,
                    baseline=None,
                    revised=_tag_snapshot(rev),
                    summary=f"Tag added: {name} ({rev.get('data_type')}) value={rev.get('value')!r}",
                )
            )
            continue

        if rev is None and base is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.TAG,
                    operation=DiffOperation.REMOVED,
                    change_class=_classify_tag(name, base, None),
                    location=f"ControllerTag/{name}",
                    tag_name=name,
                    canonical_name=identity.canonical_name,
                    equipment=equipment,
                    baseline=_tag_snapshot(base),
                    revised=None,
                    summary=f"Tag removed: {name} ({base.get('data_type')}) value={base.get('value')!r}",
                )
            )
            continue

        assert base is not None and rev is not None
        if not _tags_logically_equal(base, rev):
            field_deltas = _tag_field_deltas(base, rev)
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.TAG,
                    operation=DiffOperation.MODIFIED,
                    change_class=_classify_tag(name, rev, base),
                    location=f"ControllerTag/{name}",
                    tag_name=name,
                    canonical_name=identity.canonical_name,
                    equipment=equipment,
                    baseline=_tag_snapshot(base),
                    revised=_tag_snapshot(rev),
                    summary=(
                        f"Tag modified: {name} "
                        + ", ".join(
                            f"{k}: {base.get(k)!r} -> {rev.get(k)!r}"
                            for k in field_deltas
                        )
                    ),
                )
            )
    return changes


def _tag_snapshot(tag: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tag.get("name"),
        "data_type": tag.get("data_type"),
        "tag_type": tag.get("tag_type"),
        "constant": tag.get("constant"),
        "value": tag.get("value"),
        "description": tag.get("description"),
        "canonical_name": normalize_tag_name(tag.get("name")),
        "equipment": extract_equipment_from_tag(tag.get("name")),
    }


def _tags_logically_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    for field in _TAG_COMPARE_FIELDS:
        if field == "description":
            # Description is documentation; treat pure whitespace diffs as noise.
            if normalize_logic_text(str(a.get(field) or "")) != normalize_logic_text(
                str(b.get(field) or "")
            ):
                # Use softer normalize for prose
                da = " ".join(str(a.get(field) or "").split())
                db = " ".join(str(b.get(field) or "").split())
                if da != db:
                    return False
        elif field == "value":
            if _normalize_value(a.get(field)) != _normalize_value(b.get(field)):
                return False
        else:
            if a.get(field) != b.get(field):
                return False
    return True


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # Normalize numeric string forms: 18.0 == 18
    try:
        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            num = float(text)
            if num.is_integer():
                return str(int(num))
            return str(num)
    except ValueError:
        pass
    return text


def _tag_field_deltas(base: dict[str, Any], rev: dict[str, Any]) -> list[str]:
    deltas: list[str] = []
    for field in _TAG_COMPARE_FIELDS:
        if field == "value":
            if _normalize_value(base.get(field)) != _normalize_value(rev.get(field)):
                deltas.append(field)
        elif field == "description":
            da = " ".join(str(base.get(field) or "").split())
            db = " ".join(str(rev.get(field) or "").split())
            if da != db:
                deltas.append(field)
        elif base.get(field) != rev.get(field):
            deltas.append(field)
    return deltas


# ---------------------------------------------------------------------------
# Program / routine / rung diff
# ---------------------------------------------------------------------------


def _diff_programs(
    baseline_programs: dict[str, dict[str, Any]],
    revised_programs: dict[str, dict[str, Any]],
) -> list[BehavioralChange]:
    changes: list[BehavioralChange] = []
    all_programs = sorted(set(baseline_programs) | set(revised_programs))

    for prog_name in all_programs:
        base_prog = baseline_programs.get(prog_name)
        rev_prog = revised_programs.get(prog_name)

        if base_prog is None and rev_prog is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.PROGRAM,
                    operation=DiffOperation.ADDED,
                    change_class=ChangeClass.SEQUENCES,
                    location=f"Program/{prog_name}",
                    baseline=None,
                    revised={"name": prog_name, "main_routine": rev_prog.get("main_routine")},
                    summary=f"Program added: {prog_name}",
                )
            )
            # Still report nested routines as added context via routine/rung diffs
            changes.extend(_diff_routines(prog_name, {}, rev_prog.get("routines", {})))
            continue

        if rev_prog is None and base_prog is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.PROGRAM,
                    operation=DiffOperation.REMOVED,
                    change_class=ChangeClass.SEQUENCES,
                    location=f"Program/{prog_name}",
                    baseline={"name": prog_name, "main_routine": base_prog.get("main_routine")},
                    revised=None,
                    summary=f"Program removed: {prog_name}",
                )
            )
            changes.extend(_diff_routines(prog_name, base_prog.get("routines", {}), {}))
            continue

        assert base_prog is not None and rev_prog is not None
        changes.extend(
            _diff_routines(
                prog_name,
                base_prog.get("routines", {}),
                rev_prog.get("routines", {}),
            )
        )
    return changes


def _diff_routines(
    program_name: str,
    baseline_routines: dict[str, dict[str, Any]],
    revised_routines: dict[str, dict[str, Any]],
) -> list[BehavioralChange]:
    changes: list[BehavioralChange] = []
    all_routines = sorted(set(baseline_routines) | set(revised_routines))

    for rout_name in all_routines:
        base_r = baseline_routines.get(rout_name)
        rev_r = revised_routines.get(rout_name)
        location_prefix = f"{program_name}/{rout_name}"

        if base_r is None and rev_r is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.ROUTINE,
                    operation=DiffOperation.ADDED,
                    change_class=_classify_routine(rout_name),
                    location=location_prefix,
                    baseline=None,
                    revised={
                        "name": rout_name,
                        "type": rev_r.get("type"),
                        "rung_count": rev_r.get("rung_count"),
                    },
                    summary=f"Routine added: {location_prefix}",
                )
            )
            changes.extend(
                _diff_rungs(program_name, rout_name, [], rev_r.get("rungs", []))
            )
            continue

        if rev_r is None and base_r is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.ROUTINE,
                    operation=DiffOperation.REMOVED,
                    change_class=_classify_routine(rout_name),
                    location=location_prefix,
                    baseline={
                        "name": rout_name,
                        "type": base_r.get("type"),
                        "rung_count": base_r.get("rung_count"),
                    },
                    revised=None,
                    summary=f"Routine removed: {location_prefix}",
                )
            )
            changes.extend(
                _diff_rungs(program_name, rout_name, base_r.get("rungs", []), [])
            )
            continue

        assert base_r is not None and rev_r is not None
        changes.extend(
            _diff_rungs(
                program_name,
                rout_name,
                base_r.get("rungs", []),
                rev_r.get("rungs", []),
            )
        )
    return changes


def _diff_rungs(
    program_name: str,
    routine_name: str,
    baseline_rungs: list[dict[str, Any]],
    revised_rungs: list[dict[str, Any]],
) -> list[BehavioralChange]:
    changes: list[BehavioralChange] = []
    base_map = {r.get("number"): r for r in baseline_rungs}
    rev_map = {r.get("number"): r for r in revised_rungs}
    all_numbers = sorted(
        set(base_map) | set(rev_map),
        key=lambda n: (n is None, n if n is not None else 0),
    )

    for number in all_numbers:
        base = base_map.get(number)
        rev = rev_map.get(number)
        location = f"{program_name}/{routine_name}/rung:{number}"

        if base is None and rev is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.RUNG,
                    operation=DiffOperation.ADDED,
                    change_class=_classify_rung(routine_name, rev.get("text"), rev.get("comment")),
                    location=location,
                    equipment=_equipment_from_logic(rev.get("text")),
                    baseline=None,
                    revised=_rung_snapshot(rev),
                    summary=f"Rung added at {location}: {rev.get('text')}",
                )
            )
            continue

        if rev is None and base is not None:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.RUNG,
                    operation=DiffOperation.REMOVED,
                    change_class=_classify_rung(routine_name, base.get("text"), base.get("comment")),
                    location=location,
                    equipment=_equipment_from_logic(base.get("text")),
                    baseline=_rung_snapshot(base),
                    revised=None,
                    summary=f"Rung removed at {location}: {base.get('text')}",
                )
            )
            continue

        assert base is not None and rev is not None
        base_logic = normalize_logic_text(base.get("text"))
        rev_logic = normalize_logic_text(rev.get("text"))
        # Behavioral: logic text only. Comment-only edits are documentation noise.
        if base_logic != rev_logic:
            changes.append(
                BehavioralChange(
                    change_id="pending",
                    artifact_type=DiffArtifactType.RUNG,
                    operation=DiffOperation.MODIFIED,
                    change_class=_classify_rung(
                        routine_name, rev.get("text") or base.get("text"), rev.get("comment")
                    ),
                    location=location,
                    equipment=_equipment_from_logic(rev.get("text") or base.get("text")),
                    baseline=_rung_snapshot(base),
                    revised=_rung_snapshot(rev),
                    summary=(
                        f"Rung logic modified at {location}: "
                        f"{base.get('text')!r} -> {rev.get('text')!r}"
                    ),
                )
            )
    return changes


def _rung_snapshot(rung: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": rung.get("number"),
        "type": rung.get("type"),
        "comment": rung.get("comment"),
        "text": rung.get("text"),
        "normalized_text": normalize_logic_text(rung.get("text")),
    }


def _equipment_from_logic(text: str | None) -> str | None:
    if not text:
        return None
    # Prefer first equipment-like token inside instruction arguments.
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text):
        equip = extract_equipment_from_tag(token)
        if equip:
            return equip
    return None


# ---------------------------------------------------------------------------
# Change classification (rule-based, deterministic)
# ---------------------------------------------------------------------------


def _classify_tag(
    name: str,
    primary: dict[str, Any],
    secondary: dict[str, Any] | None,
) -> ChangeClass:
    upper = name.upper()
    desc = (primary.get("description") or "").upper()
    if upper.startswith("ALM_") or "ALARM" in upper or "ALARM" in desc:
        return ChangeClass.ALARMS_TIMERS
    if upper.startswith("TMR_") or "TIMEOUT" in upper or "DELAY" in upper:
        return ChangeClass.ALARMS_TIMERS
    if upper.startswith("CFG_") and any(
        k in upper for k in ("TIMEOUT", "DELAY", "ALARM", "TRIP", "HIGH", "LOW", "SP")
    ):
        # Trip/alarm thresholds and timer presets
        if any(k in upper for k in ("TIMEOUT", "DELAY", "ALARM", "TRIP", "HIGH", "LOW")):
            return ChangeClass.ALARMS_TIMERS
        if upper.endswith("_SP") or "_SP_" in upper:
            return ChangeClass.ALARMS_TIMERS
    if any(k in upper for k in ("HAND", "AUTO", "MODE", "ENABLE", "MANUAL")):
        return ChangeClass.MODES
    if any(k in upper for k in ("PERMISSIVE", "INTERLOCK", "EPO", "LEAK", "FIRE")):
        return ChangeClass.INTERLOCKS
    if any(
        k in upper
        for k in (
            "POSTRUN",
            "SEQUENCE",
            "FAILOVER",
            "LEAD",
            "ROTATION",
            "REQUEST",
            "RUNREQUEST",
        )
    ):
        return ChangeClass.SEQUENCES
    if upper.startswith("CFG_"):
        return ChangeClass.SEQUENCES
    return ChangeClass.SEQUENCES


def _classify_routine(routine_name: str) -> ChangeClass:
    upper = routine_name.upper()
    if "ALARM" in upper:
        return ChangeClass.ALARMS_TIMERS
    if "SEQUENCE" in upper:
        return ChangeClass.SEQUENCES
    if "CONTROL" in upper:
        return ChangeClass.INTERLOCKS
    return ChangeClass.SEQUENCES


def _classify_rung(
    routine_name: str,
    text: str | None,
    comment: str | None,
) -> ChangeClass:
    blob = f"{routine_name} {text or ''} {comment or ''}".upper()

    if "AFI(" in blob or "AFI()" in blob:
        return ChangeClass.SEQUENCES  # disabled failover / sequence branch
    # Mode/HMI command wiring before permissive keyword (permissives often co-occur).
    if any(k in blob for k in ("HANDCMD", "AUTOENABLE", "MODE", "MANUAL")):
        return ChangeClass.MODES
    if any(k in blob for k in ("TON(", "TOF(", "RTO(", "TIMEOUT", "DELAY", "ALM_", "TMR_")):
        return ChangeClass.ALARMS_TIMERS
    if any(k in blob for k in ("PERMISSIVE", "INTERLOCK", "LEAK", "FIRE", "EPO")):
        return ChangeClass.INTERLOCKS
    if any(k in blob for k in ("FAILOVER", "POSTRUN", "SEQUENCE", "LEAD", "JSR(")):
        return ChangeClass.SEQUENCES
    if "ALARM" in routine_name.upper():
        return ChangeClass.ALARMS_TIMERS
    if "CONTROL" in routine_name.upper():
        return ChangeClass.INTERLOCKS
    return ChangeClass.SEQUENCES


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _build_summary(changes: list[BehavioralChange]) -> DiffSummary:
    by_class: dict[str, int] = {c.value: 0 for c in ChangeClass}
    by_op: dict[str, int] = {o.value: 0 for o in DiffOperation}
    tag_n = rung_n = routine_n = program_n = 0

    for change in changes:
        by_class[change.change_class.value] = by_class.get(change.change_class.value, 0) + 1
        by_op[change.operation.value] = by_op.get(change.operation.value, 0) + 1
        if change.artifact_type == DiffArtifactType.TAG:
            tag_n += 1
        elif change.artifact_type == DiffArtifactType.RUNG:
            rung_n += 1
        elif change.artifact_type == DiffArtifactType.ROUTINE:
            routine_n += 1
        elif change.artifact_type == DiffArtifactType.PROGRAM:
            program_n += 1

    return DiffSummary(
        tag_changes=tag_n,
        rung_changes=rung_n,
        routine_changes=routine_n,
        program_changes=program_n,
        total_changes=len(changes),
        by_change_class=by_class,
        by_operation=by_op,
    )
