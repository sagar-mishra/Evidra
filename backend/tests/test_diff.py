"""
Milestone 2 validation script — Deterministic Diff & Normalization.

Compares baseline vs revised L5X under sample_data/ and prints true
behavioral differences while ignoring export metadata noise.

Usage (from project root):
    uv run python backend/tests/test_diff.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.schemas.change_models import ChangeClass, DiffArtifactType
from app.services.diff_engine import DiffEngineError, diff_l5x_files
from app.services.name_normalizer import (
    names_equivalent,
    normalize_equipment_name,
    normalize_identity,
    normalize_tag_name,
)

# backend/tests/ -> ../../sample_data/
SAMPLE_DIR = (Path(__file__).resolve().parent / ".." / ".." / "sample_data").resolve()

BASELINE_L5X = SAMPLE_DIR / "DC1_Cooling_Baseline_RevA.L5X"
REVISED_L5X = SAMPLE_DIR / "DC1_Cooling_Revised_RevB.L5X"

# DC1 VALIDATION_REPORT: 7 initialized tag values + 9 ladder rungs.
EXPECTED_TAG_CHANGES = 7
EXPECTED_RUNG_CHANGES = 9
EXPECTED_TOTAL = EXPECTED_TAG_CHANGES + EXPECTED_RUNG_CHANGES

# Ground-truth tag setpoints that must appear in the diff.
EXPECTED_TAG_NAMES = {
    "CFG_CHW_DP_SP",
    "CFG_PumpFlowProofTimeout_ms",
    "CFG_SAT_High_SP",
    "CFG_CHW_SuctionLowTrip_SP",
    "CFG_CHW_DP_LowAlarm_SP",
    "CFG_LeadRotation_hr",
    "CFG_PumpPostRun_ms",
}

# Ground-truth rung locations (program/routine/rung).
EXPECTED_RUNG_LOCATIONS = {
    "P_DC_Cooling/R30_CHWP_Control/rung:2",
    "P_DC_Cooling/R30_CHWP_Control/rung:3",
    "P_DC_Cooling/R30_CHWP_Control/rung:5",
    "P_DC_Cooling/R30_CHWP_Control/rung:9",
    "P_DC_Cooling/R40_AHU_Control/rung:3",
    "P_DC_Cooling/R40_AHU_Control/rung:5",
    "P_DC_Cooling/R40_AHU_Control/rung:6",
    "P_DC_Cooling/R50_Alarms/rung:13",
    "P_DC_Cooling/R50_Alarms/rung:15",
}


def _divider(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _print_normalization_demo() -> None:
    _divider("NAME NORMALIZATION (sample)")
    samples = [
        "AHU-01_Permissive",
        "AHU01_Permissive",
        "ahu_01_permissive",
        "CHWP-02_FailoverRequest",
        "CFG_CHW_DP_SP",
        "HMI_AHU02_HandCmd",
    ]
    for raw in samples:
        ident = normalize_identity(raw)
        print(
            f"  {raw:28s} -> canonical={ident.canonical_name:28s} "
            f"equipment={ident.equipment!s:8s} role={ident.role}"
        )

    assert names_equivalent("AHU-01_Permissive", "AHU01_Permissive")
    assert names_equivalent("CHWP-02", "CHWP02")
    assert normalize_equipment_name("AHU-01") == normalize_equipment_name("AHU01")
    assert normalize_tag_name("cfg_chw_dp_sp") == "CFG_CHW_DP_SP"
    print("\n  Normalization self-checks: PASSED")


def _print_changes(report) -> None:
    _divider("BEHAVIORAL TAG CHANGES")
    tag_changes = [c for c in report.changes if c.artifact_type == DiffArtifactType.TAG]
    for change in tag_changes:
        print(f"  [{change.change_id}] {change.operation.value:8s}  {change.change_class.value}")
        print(f"    location : {change.location}")
        print(f"    canonical: {change.canonical_name}  equipment={change.equipment}")
        bval = (change.baseline or {}).get("value")
        rval = (change.revised or {}).get("value")
        print(f"    value    : {bval!r} -> {rval!r}")
        print(f"    summary  : {change.summary}")

    _divider("BEHAVIORAL RUNG CHANGES")
    rung_changes = [c for c in report.changes if c.artifact_type == DiffArtifactType.RUNG]
    for change in rung_changes:
        print(f"  [{change.change_id}] {change.operation.value:8s}  {change.change_class.value}")
        print(f"    location : {change.location}")
        print(f"    equipment: {change.equipment}")
        btext = (change.baseline or {}).get("text")
        rtext = (change.revised or {}).get("text")
        print(f"    baseline : {btext}")
        print(f"    revised  : {rtext}")

    other = [
        c
        for c in report.changes
        if c.artifact_type not in (DiffArtifactType.TAG, DiffArtifactType.RUNG)
    ]
    if other:
        _divider("OTHER STRUCTURAL CHANGES")
        for change in other:
            print(f"  [{change.change_id}] {change.artifact_type.value} {change.summary}")


def _validate(report) -> list[str]:
    """Return list of validation failures (empty == pass)."""
    failures: list[str] = []
    s = report.summary

    if s.tag_changes != EXPECTED_TAG_CHANGES:
        failures.append(
            f"tag_changes={s.tag_changes}, expected {EXPECTED_TAG_CHANGES}"
        )
    if s.rung_changes != EXPECTED_RUNG_CHANGES:
        failures.append(
            f"rung_changes={s.rung_changes}, expected {EXPECTED_RUNG_CHANGES}"
        )
    if s.total_changes != EXPECTED_TOTAL:
        failures.append(
            f"total_changes={s.total_changes}, expected {EXPECTED_TOTAL}"
        )

    found_tags = {
        c.tag_name
        for c in report.changes
        if c.artifact_type == DiffArtifactType.TAG and c.tag_name
    }
    missing_tags = EXPECTED_TAG_NAMES - found_tags
    extra_tags = found_tags - EXPECTED_TAG_NAMES
    if missing_tags:
        failures.append(f"missing expected tag diffs: {sorted(missing_tags)}")
    if extra_tags:
        failures.append(f"unexpected tag diffs: {sorted(extra_tags)}")

    found_rungs = {
        c.location
        for c in report.changes
        if c.artifact_type == DiffArtifactType.RUNG
    }
    missing_rungs = EXPECTED_RUNG_LOCATIONS - found_rungs
    extra_rungs = found_rungs - EXPECTED_RUNG_LOCATIONS
    if missing_rungs:
        failures.append(f"missing expected rung diffs: {sorted(missing_rungs)}")
    if extra_rungs:
        failures.append(f"unexpected rung diffs: {sorted(extra_rungs)}")

    # Metadata noise must never appear as a change location/summary.
    noise_tokens = ("ExportDate", "ToolID", "LastModifiedDate", "ProjectCreationDate")
    for change in report.changes:
        blob = f"{change.location} {change.summary}"
        for token in noise_tokens:
            if token in blob:
                failures.append(f"metadata noise leaked into diff: {token} in {change.change_id}")

    # All changes must carry a frozen change class.
    for change in report.changes:
        if change.change_class not in ChangeClass:
            failures.append(f"{change.change_id} has invalid change_class")

    return failures


def main() -> None:
    print("Milestone 2 — Deterministic Diff & Normalization")
    print(f"Sample directory: {SAMPLE_DIR.as_posix()}")

    missing = [p for p in (BASELINE_L5X, REVISED_L5X) if not p.is_file()]
    if missing:
        print("ERROR: Missing sample files:", file=sys.stderr)
        for p in missing:
            print(f"  - {p.as_posix()}", file=sys.stderr)
        raise SystemExit(1)

    _print_normalization_demo()

    try:
        report = diff_l5x_files(BASELINE_L5X, REVISED_L5X)
    except DiffEngineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _divider("DIFF REPORT HEADER")
    print(f"Baseline   : {report.baseline_source}")
    print(f"Revised    : {report.revised_source}")
    print(f"Controller : {report.baseline_controller} -> {report.revised_controller}")
    print(f"Ignored    : {report.ignored_noise_categories}")

    _print_changes(report)

    _divider("DIFF SUMMARY")
    print(report.summary.model_dump_json(indent=2))

    failures = _validate(report)
    _divider("VALIDATION")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "failures": failures,
                    "summary": report.summary.model_dump(),
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    print("All Milestone 2 checks PASSED.")
    print(
        json.dumps(
            {
                "status": "OK",
                "tag_changes": report.summary.tag_changes,
                "rung_changes": report.summary.rung_changes,
                "total_changes": report.summary.total_changes,
                "by_change_class": report.summary.by_change_class,
                "expected_tag_changes": EXPECTED_TAG_CHANGES,
                "expected_rung_changes": EXPECTED_RUNG_CHANGES,
            },
            indent=2,
        )
    )
    print("\nMilestone 2 deterministic diff completed successfully.")


if __name__ == "__main__":
    main()
