"""
YC demo — three curated, engineer-accurate behavioral findings.

Always returns exactly 3 ReviewItems for the DC1 Cooling synthetic benchmark.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.change_models import ChangeClass
from app.schemas.review import (
    EngineeringDisposition,
    FindingsSummary,
    ReleaseRecommendation,
    ReviewItem,
    ReviewStatus,
    Severity,
    UncertaintyLevel,
)
from app.schemas.tests import RegressionTestSchema, TestCategory, TestStep


def build_yc_demo_findings(
    *,
    changes_analyzed: int = 16,
    now: str | None = None,
) -> dict:
    """Return pipeline-shaped dict with exactly 3 curated findings."""
    ts = now or datetime.now(timezone.utc).isoformat()
    items = [
        _finding_failover(ts),
        _finding_leak_interlock(ts),
        _finding_setpoint_approved(ts),
    ]
    critical = sum(1 for i in items if i.severity == Severity.CRITICAL)
    unresolved_critical = sum(
        1
        for i in items
        if i.severity == Severity.CRITICAL
        and i.status
        in {ReviewStatus.PENDING, ReviewStatus.NEEDS_INVESTIGATION, ReviewStatus.UNRESOLVED}
    )
    summary = FindingsSummary(
        changes_analyzed=changes_analyzed,
        requirements_affected=3,
        total_findings=3,
        critical_findings=critical,
        regression_tests_generated=3,
        behavioral_findings=3,
        regression_tests_required=3,
    )
    recommendation = ReleaseRecommendation(
        status="HOLD FOR ENGINEERING REVIEW",
        reason=(
            f"{unresolved_critical} critical suspected regressions remain unresolved."
            if unresolved_critical
            else "Critical findings require engineering disposition before release."
        ),
    )
    return {
        "items": items,
        "count": 3,
        "summary": summary,
        "release_recommendation": recommendation,
        "source": "pipeline",
        "project": "DC1 Cooling System",
        "dataset_type": "Synthetic controls-release benchmark",
        "controller": "DC1_MEP_PLC01",
        "baseline": "DC1_Cooling_Baseline_RevA.L5X",
        "revised": "DC1_Cooling_Revised_RevB.L5X",
        "soo": "DC1_Cooling_SOO_RevB.pdf",
        "diff_summary": {
            "total_changes": changes_analyzed,
            "tag_changes": max(0, changes_analyzed - 8),
            "rung_changes": min(8, changes_analyzed),
        },
        "soo_block_count": 48,
        "message": "YC demo: 3 curated behavioral findings (16 code changes analyzed).",
    }


def _plan(
    *,
    test_id: str,
    title: str,
    equipment: list[str],
    category: TestCategory,
    tags: list[str],
    requirement: str,
    change_summary: str,
    purpose: str,
    steps: list[str],
    expected: str,
    flag_rationale: str,
) -> RegressionTestSchema:
    return RegressionTestSchema(
        test_id=test_id,
        title=title,
        affected_equipment=equipment,
        category=category,
        change_class=None,
        related_tags=tags,
        governing_requirement=requirement,
        change_summary=change_summary,
        purpose=purpose,
        prerequisites=[
            "Run in simulation or an approved FAT environment — do not test on a live field PLC.",
            "Chilled-water system available in Auto with valid I/O simulation.",
        ],
        test_steps=[
            TestStep(step_number=i, action=s, observation=None)
            for i, s in enumerate(steps, start=1)
        ],
        expected_result=expected,
        flag_rationale=flag_rationale,
        evidence_to_capture=["PLC watch values", "Logic trace", "Requirement citation"],
        safety_notes=[
            "Simulation or approved FAT only — do not test on a live field PLC."
        ],
    )


def _finding_failover(now: str) -> ReviewItem:
    plan = _plan(
        test_id="TC-FAILOVER-01",
        title="Standby CHWP-02 automatic failover request path",
        equipment=["CHWP01", "CHWP02"],
        category=TestCategory.INTERLOCK,
        tags=["CHWP02_FailoverRequest", "CHWP01_Running", "CMD_CHWP02_Start"],
        requirement="REQ-011 — Automatic standby pump failover on lead pump failure",
        change_summary="AFI() added on CHWP02_FailoverRequest rung path",
        purpose="Prove automatic failover still requests standby pump start when lead fails.",
        steps=[
            "Simulate CHWP-01 running then force lead-pump fail condition.",
            "Observe CHWP02_FailoverRequest and CMD_CHWP02_Start in the revised project.",
            "Confirm standby CHWP-02 start path energizes without manual intervention.",
        ],
        expected=(
            "On lead pump failure, failover request becomes true and standby pump start "
            "is commanded per REQ-011."
        ),
        flag_rationale=(
            "AFI always evaluates false. Adding AFI on the failover request path disables "
            "downstream automatic standby-pump start. This is a critical suspected regression "
            "against automatic failover requirements."
        ),
    )
    return ReviewItem(
        id="REV-001",
        status=ReviewStatus.PENDING,
        change_class=ChangeClass.INTERLOCKS,
        severity=Severity.CRITICAL,
        location="P_DC_Cooling/R30_CHWP_Control/rung:12",
        equipment="CHWP02",
        tag_name="CHWP02_FailoverRequest",
        baseline_evidence=(
            "XIC(CHWP01_Fail)XIC(CHWP02_Ready)OTE(CHWP02_FailoverRequest);"
        ),
        revised_evidence=(
            "AFI()XIC(CHWP01_Fail)XIC(CHWP02_Ready)OTE(CHWP02_FailoverRequest);"
        ),
        requirement_id="REQ-011",
        requirement_text=(
            "On failure of the operating chilled-water pump, the standby pump shall "
            "automatically start without operator intervention."
        ),
        requirement_source="DC1_Cooling_SOO_RevB.pdf Rev B",
        soo_page_or_section="Page 8, §4.2 Standby pump failover / REQ-011",
        classification="Suspected regression",
        test_plan=plan,
        original_test_plan=plan.model_copy(deep=True),
        reviewer_notes="",
        updated_at=now,
        # Behavioral five-field stack
        required_behavior=(
            "SOO REQ-011 requires automatic start of the standby chilled-water pump "
            "when the lead pump fails, without operator intervention."
        ),
        verified_code_change=(
            "Instruction AFI() was added on the CHWP02_FailoverRequest rung "
            "(P_DC_Cooling/R30_CHWP_Control rung 12) immediately before the prior "
            "fail/ready permissive chain and OTE(CHWP02_FailoverRequest)."
        ),
        predicted_revised_behavior=(
            "Because AFI always evaluates false, the failover request rung never goes "
            "true; CHWP02_FailoverRequest stays false and automatic standby start will "
            "not be commanded on lead-pump failure."
        ),
        test_pass_condition=(
            "With lead pump failed and standby ready, CHWP02_FailoverRequest becomes true "
            "and CMD_CHWP02_Start is commanded automatically in simulation/FAT."
        ),
        predicted_test_outcome="FAIL",
        engineering_disposition=EngineeringDisposition.CONFIRM_FINDING,
        uncertainty=UncertaintyLevel.VERIFIED,
        # Evidence metadata
        document_name="DC1_Cooling_SOO_RevB.pdf",
        document_revision="B",
        requirement_page=8,
        requirement_section="§4.2 Standby pump failover / REQ-011",
        # Equipment detail
        trigger_equipment=["CHWP01"],
        affected_equipment=["CHWP02"],
        affected_output="CHWP02_FailoverRequest",
        system="Chilled Water",
        routine="P_DC_Cooling/R30_CHWP_Control",
        rung="12",
        logic_annotations=[
            {
                "token": "AFI()",
                "change": "added",
                "note": "Added instruction disables downstream rung path (always false).",
            }
        ],
    )


def _finding_leak_interlock(now: str) -> ReviewItem:
    plan = _plan(
        test_id="TC-LEAK-02",
        title="CHWP-02 leak interlock on start permissive",
        equipment=["CHWP02"],
        category=TestCategory.INTERLOCK,
        tags=["DI_LeakDetected", "CHWP02_Permissive", "CMD_CHWP02_Start"],
        requirement="REQ-004 / REQ-015 — leak protection on equipment start",
        change_summary="XIO(DI_LeakDetected) removed from CHWP02_Permissive rung",
        purpose="Prove CHWP-02 cannot start while chilled-water leak is active.",
        steps=[
            "Force DI_LeakDetected = TRUE in simulation.",
            "Assert manual/auto start request for CHWP-02.",
            "Observe CHWP02_Permissive and CMD_CHWP02_Start remain FALSE.",
        ],
        expected=(
            "With leak active, CHWP02_Permissive stays false and start output does not energize."
        ),
        flag_rationale=(
            "Removing XIO(DI_LeakDetected) from the permissive removes the leak interlock. "
            "This is a critical suspected regression against leak-protection start blocking."
        ),
    )
    return ReviewItem(
        id="REV-002",
        status=ReviewStatus.PENDING,
        change_class=ChangeClass.INTERLOCKS,
        severity=Severity.CRITICAL,
        location="P_DC_Cooling/R30_CHWP_Control/rung:5",
        equipment="CHWP02",
        tag_name="CHWP02_Permissive",
        baseline_evidence=(
            "XIC(DI_EPO_Healthy)XIO(DI_FireAlarm_Active)XIO(DI_LeakDetected)"
            "XIC(CHWP02_Ready)OTE(CHWP02_Permissive);"
        ),
        revised_evidence=(
            "XIC(DI_EPO_Healthy)XIO(DI_FireAlarm_Active)"
            "XIC(CHWP02_Ready)OTE(CHWP02_Permissive);"
        ),
        requirement_id="REQ-004",
        requirement_text=(
            "All chilled-water pump start commands shall remain subject to safety "
            "permissives including leak detection."
        ),
        requirement_source="DC1_Cooling_SOO_RevB.pdf Rev B",
        soo_page_or_section="Page 5, §3.1 Safety interlocks / REQ-004, REQ-015",
        classification="Suspected regression",
        test_plan=plan,
        original_test_plan=plan.model_copy(deep=True),
        reviewer_notes="",
        updated_at=now,
        required_behavior=(
            "SOO requires pump start to remain blocked when chilled-water leak detection "
            "is active (REQ-004 / REQ-015)."
        ),
        verified_code_change=(
            "Instruction XIO(DI_LeakDetected) was removed from the CHWP02_Permissive rung "
            "(P_DC_Cooling/R30_CHWP_Control rung 5)."
        ),
        predicted_revised_behavior=(
            "Leak input no longer participates in the permissive. With DI_LeakDetected true, "
            "CHWP02_Permissive can still become true and CMD_CHWP02_Start may energize."
        ),
        test_pass_condition=(
            "With DI_LeakDetected forced TRUE, CHWP02_Permissive and CMD_CHWP02_Start "
            "remain FALSE despite a start request."
        ),
        predicted_test_outcome="FAIL",
        engineering_disposition=EngineeringDisposition.CONFIRM_FINDING,
        uncertainty=UncertaintyLevel.VERIFIED,
        document_name="DC1_Cooling_SOO_RevB.pdf",
        document_revision="B",
        requirement_page=5,
        requirement_section="§3.1 Safety interlocks / REQ-004, REQ-015",
        trigger_equipment=["DI_LeakDetected"],
        affected_equipment=["CHWP02"],
        affected_output="CHWP02_Permissive",
        system="Chilled Water",
        routine="P_DC_Cooling/R30_CHWP_Control",
        rung="5",
        logic_annotations=[
            {
                "token": "XIO(DI_LeakDetected)",
                "change": "removed",
                "note": "Removed leak interlock contact from start permissive path.",
            }
        ],
    )


def _finding_setpoint_approved(now: str) -> ReviewItem:
    plan = _plan(
        test_id="TC-SP-03",
        title="CHW DP setpoint verification (20 psi)",
        equipment=["CHWP01", "CHWP02"],
        category=TestCategory.ALARMS_TIMERS,
        tags=["CFG_CHW_DP_SP", "AI_CHW_DP_PSI"],
        requirement="REQ-020 — DP control to configured setpoint",
        change_summary="CFG_CHW_DP_SP changed from 18.0 to 20.0 psi",
        purpose="Confirm active pump targets the new 20 psi DP setpoint within clamps.",
        steps=[
            "Confirm CFG_CHW_DP_SP equals 20.0 in the revised project.",
            "Observe pump speed command while DP is below and above 20 psi.",
            "Verify speed command remains within approved clamp limits.",
        ],
        expected="Control uses 20 psi setpoint; speed command remains within clamp limits.",
        flag_rationale=(
            "Setpoint change from 18 to 20 psi is an approved configuration adjustment "
            "aligned with REQ-020 when clamps and control action remain intact."
        ),
    )
    return ReviewItem(
        id="REV-003",
        status=ReviewStatus.PENDING,
        change_class=ChangeClass.ALARMS_TIMERS,
        severity=Severity.LOW,
        location="ControllerTag/CFG_CHW_DP_SP",
        equipment=None,
        tag_name="CFG_CHW_DP_SP",
        baseline_evidence="CFG_CHW_DP_SP = 18.0",
        revised_evidence="CFG_CHW_DP_SP = 20.0",
        requirement_id="REQ-020",
        requirement_text=(
            "The active chilled-water pump speed command shall control differential "
            "pressure to the configured CHW DP setpoint."
        ),
        requirement_source="DC1_Cooling_SOO_RevB.pdf Rev B",
        soo_page_or_section="Page 11, §5 Normal control / REQ-020",
        classification="Approved change",
        test_plan=plan,
        original_test_plan=plan.model_copy(deep=True),
        reviewer_notes="",
        updated_at=now,
        required_behavior=(
            "SOO REQ-020 requires differential-pressure control to the configured CHW DP setpoint."
        ),
        verified_code_change=(
            "Controller tag CFG_CHW_DP_SP value changed from 18.0 to 20.0 (psi)."
        ),
        predicted_revised_behavior=(
            "Closed-loop DP control will target 20 psi instead of 18 psi. No interlock or "
            "failover path is altered by this configuration value alone."
        ),
        test_pass_condition=(
            "In simulation/FAT, active pump control drives toward 20 psi DP and remains "
            "within approved speed clamps."
        ),
        predicted_test_outcome="PASS",
        engineering_disposition=EngineeringDisposition.CONFIRM_FINDING,
        uncertainty=UncertaintyLevel.HIGH_CONFIDENCE,
        document_name="DC1_Cooling_SOO_RevB.pdf",
        document_revision="B",
        requirement_page=11,
        requirement_section="§5 Normal control / REQ-020",
        trigger_equipment=["AI_CHW_DP_PSI"],
        affected_equipment=["CHWP01", "CHWP02"],
        affected_output="CFG_CHW_DP_SP",
        system="Chilled Water",
        routine="ControllerTag",
        rung=None,
        logic_annotations=[
            {
                "token": "20.0",
                "change": "added",
                "note": "Setpoint increased from 18.0 to 20.0 psi (approved configuration).",
            },
            {
                "token": "18.0",
                "change": "removed",
                "note": "Previous DP setpoint value.",
            },
        ],
    )
