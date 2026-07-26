"""
Review-item schemas shared by the mock findings API and pipeline results.

Field names are the wire contract for the Next.js client.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.change_models import ChangeClass
from app.schemas.tests import RegressionTestSchema, TestCategory, TestStep


class ReviewStatus(str, Enum):
    """Wire status — UI labels map Confirm/Dismiss/Needs Investigation onto these."""

    PENDING = "Pending"
    ACCEPTED = "Accepted"  # Confirm Finding
    REJECTED = "Rejected"  # Dismiss Finding
    EDITED = "Edited"
    UNRESOLVED = "Unresolved"
    NEEDS_INVESTIGATION = "Needs Investigation"


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class EngineeringDisposition(str, Enum):
    CONFIRM_FINDING = "CONFIRM FINDING"
    DISMISS = "DISMISS"
    NEEDS_INVESTIGATION = "NEEDS INVESTIGATION"


class UncertaintyLevel(str, Enum):
    VERIFIED = "Verified"
    HIGH_CONFIDENCE = "High confidence"
    PROBABLE = "Probable"
    UNKNOWN = "Unknown"


class ReviewItem(BaseModel):
    """
    One human-reviewable behavioral finding: L5X change + requirement + test plan.
    """

    id: str = Field(..., description="Stable review id, e.g. REV-001")
    status: ReviewStatus = Field(default=ReviewStatus.PENDING)
    change_class: ChangeClass
    severity: Severity
    location: str
    equipment: str | None = None
    tag_name: str | None = None
    baseline_evidence: str
    revised_evidence: str
    requirement_id: str
    requirement_text: str
    requirement_source: str
    soo_page_or_section: str = Field(
        ...,
        description="SOO/FDS page number, section, or block citation for evidence.",
    )
    classification: str
    test_plan: RegressionTestSchema
    original_test_plan: RegressionTestSchema
    reviewer_notes: str = ""
    updated_at: str

    # --- 5 mandatory behavioral fields ---
    required_behavior: str = Field(
        default="",
        description="What the SOO says must happen.",
    )
    verified_code_change: str = Field(
        default="",
        description="Exact instruction/tag that changed.",
    )
    predicted_revised_behavior: str = Field(
        default="",
        description="What revised logic is likely to do.",
    )
    test_pass_condition: str = Field(
        default="",
        description="Behavior required for the regression test to pass.",
    )
    predicted_test_outcome: Literal["PASS", "FAIL", "UNKNOWN"] = "UNKNOWN"

    engineering_disposition: EngineeringDisposition = (
        EngineeringDisposition.NEEDS_INVESTIGATION
    )
    uncertainty: UncertaintyLevel = UncertaintyLevel.PROBABLE

    # Requirement evidence metadata
    document_name: str = ""
    document_revision: str = ""
    requirement_page: int = 0
    requirement_section: str = ""

    # Equipment detail
    trigger_equipment: list[str] = Field(default_factory=list)
    affected_equipment: list[str] = Field(default_factory=list)
    affected_output: str = ""
    system: str = ""
    routine: str = ""
    rung: str | None = None

    # Side-by-side logic annotations (token highlights)
    logic_annotations: list[dict[str, Any]] = Field(default_factory=list)


class FindingsSummary(BaseModel):
    """Compact explainability metrics for the dashboard ribbon."""

    changes_analyzed: int = Field(..., ge=0)
    requirements_affected: int = Field(default=0, ge=0)
    total_findings: int = Field(..., ge=0)
    critical_findings: int = Field(..., ge=0)
    regression_tests_generated: int = Field(default=0, ge=0)
    # YC demo ribbon labels
    behavioral_findings: int = Field(default=0, ge=0)
    regression_tests_required: int = Field(default=0, ge=0)


class ReleaseRecommendation(BaseModel):
    status: str = "HOLD FOR ENGINEERING REVIEW"
    reason: str = "Critical suspected regressions remain unresolved."


class MockFindingsResponse(BaseModel):
    """GET /api/v1/mock-findings response envelope."""

    items: list[ReviewItem]
    count: int
    summary: FindingsSummary
    source: Literal["mock"] = "mock"
    project: str = "DC1 Cooling System"
    dataset_type: str = "Synthetic controls-release benchmark"
    controller: str = "DC1_MEP_PLC01"
    baseline: str = "DC1_Cooling_Baseline_RevA.L5X"
    revised: str = "DC1_Cooling_Revised_RevB.L5X"
    soo: str | None = "DC1_Cooling_SOO_RevB.pdf"
    release_recommendation: ReleaseRecommendation = Field(
        default_factory=ReleaseRecommendation
    )


class AnalyzeResponse(BaseModel):
    """POST /api/v1/analyze response envelope (real pipeline)."""

    items: list[ReviewItem]
    count: int
    summary: FindingsSummary
    source: Literal["pipeline"] = "pipeline"
    project: str
    dataset_type: str = "Synthetic controls-release benchmark"
    controller: str
    baseline: str
    revised: str
    soo: str | None = None
    governing_docs: list[str] | None = None
    diff_summary: dict[str, int] | None = None
    soo_block_count: int | None = None
    message: str | None = None
    release_recommendation: ReleaseRecommendation | None = None


def build_findings_summary(
    items: list[ReviewItem],
    *,
    changes_analyzed: int | None = None,
) -> FindingsSummary:
    """Compute dashboard metrics from a findings list."""
    req_ids = {i.requirement_id for i in items if (i.requirement_id or "").strip()}
    critical = sum(1 for i in items if i.severity == Severity.CRITICAL)
    n = len(items)
    return FindingsSummary(
        changes_analyzed=changes_analyzed if changes_analyzed is not None else n,
        requirements_affected=len(req_ids),
        total_findings=n,
        critical_findings=critical,
        regression_tests_generated=sum(1 for i in items if i.test_plan is not None),
        behavioral_findings=n,
        regression_tests_required=n,
    )


__all__ = [
    "AnalyzeResponse",
    "ChangeClass",
    "EngineeringDisposition",
    "FindingsSummary",
    "MockFindingsResponse",
    "RegressionTestSchema",
    "ReleaseRecommendation",
    "ReviewItem",
    "ReviewStatus",
    "Severity",
    "TestCategory",
    "TestStep",
    "UncertaintyLevel",
    "build_findings_summary",
]
