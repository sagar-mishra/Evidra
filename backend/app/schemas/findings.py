"""
Strict Pydantic schemas for constrained PLC release-review reasoning.

The LLM may only fill these structures from supplied parser facts + industrial rules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StructuredPlcChange(BaseModel):
    """
    Deterministic extraction for a changed rung/tag (no LLM).

    Produced by ``app.services.parser``.
    """

    routine: str = Field(..., description="Routine name or ControllerTag scope")
    rung_number: int | None = Field(
        default=None, description="Rung number when applicable"
    )
    baseline_logic: str = Field(default="", description="Baseline ladder text or value")
    revised_logic: str = Field(default="", description="Revised ladder text or value")
    instructions_added: list[str] = Field(default_factory=list)
    instructions_removed: list[str] = Field(default_factory=list)
    output_tags: list[str] = Field(default_factory=list)
    input_tags: list[str] = Field(default_factory=list)
    # Extra context for pipeline (not always shown in UI stack)
    location: str | None = None
    change_id: str | None = None
    equipment: str | None = None
    tag_name: str | None = None


class RequirementMapping(BaseModel):
    """Strict format for a mapped governing requirement."""

    document: str = Field(..., min_length=1, description="SOO/FDS document name")
    revision: str = Field(default="", description="Document revision if known")
    page: int = Field(default=0, ge=0, description="Page number (0 if unknown)")
    section: str = Field(default="", description="Section heading or block id")
    requirement_text: str = Field(..., min_length=1)
    mapping_reason: str = Field(
        ...,
        min_length=1,
        description="Why this requirement was linked to the PLC change",
    )


class BehavioralFinding(BaseModel):
    """
    Strict 5-field behavioral finding (YC engineering accuracy contract).
    """

    required_behavior: str = Field(
        ...,
        min_length=1,
        description="What the SOO says must happen",
    )
    verified_code_change: str = Field(
        ...,
        min_length=1,
        description="Exact instruction/tag that changed",
    )
    predicted_revised_behavior: str = Field(
        ...,
        min_length=1,
        description="What revised logic is likely to do",
    )
    test_pass_condition: str = Field(
        ...,
        min_length=1,
        description="Behavior required for the regression test to pass",
    )
    predicted_test_outcome: Literal["PASS", "FAIL", "UNKNOWN"] = Field(
        ...,
        description="Predicted FAT outcome",
    )


class ConstrainedFinding(BaseModel):
    """
    Strict finding output from the constrained reasoning LLM call
    (``LLM_REASONING_MODEL``). Also referred to as StrictFindingSchema.
    """

    title: str = Field(..., min_length=1)
    classification: Literal[
        "Approved change",
        "Suspected regression",
        "Needs review",
    ]
    # Legacy fields retained for back-compat with older generators
    verified_change: str = Field(
        ...,
        min_length=1,
        description="Only facts verified from structured PLC change data",
    )
    likely_behavioral_impact: str = Field(
        ...,
        min_length=1,
        description="Impact inferred only from supplied industrial rules",
    )
    requirement_relationship: str = Field(
        ...,
        min_length=1,
        description="How the change relates to the candidate SOO requirement",
    )
    # Mandatory 5-field behavioral stack
    required_behavior: str = Field(default="", description="What SOO requires")
    verified_code_change: str = Field(
        default="", description="Exact code change (instruction/tag)"
    )
    predicted_revised_behavior: str = Field(
        default="", description="Predicted revised process/PLC behavior"
    )
    test_pass_condition: str = Field(
        default="", description="Condition under which regression test passes"
    )
    predicted_test_outcome: Literal["PASS", "FAIL", "UNKNOWN"] = "UNKNOWN"
    engineering_disposition: Literal[
        "CONFIRM FINDING",
        "DISMISS",
        "NEEDS INVESTIGATION",
    ] = "NEEDS INVESTIGATION"
    uncertainty: Literal[
        "Verified",
        "High confidence",
        "Probable",
        "Unknown",
    ] = "Probable"
    unknowns: list[str] = Field(
        default_factory=list,
        description="Items that cannot be determined from supplied facts",
    )
    severity: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    test_title: str = Field(..., min_length=1)
    test_prerequisites: list[str] = Field(..., min_length=1)
    test_steps: list[str] = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)

    @field_validator("test_prerequisites")
    @classmethod
    def _require_sim_or_fat(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("test_prerequisites must not be empty")
        blob = " ".join(cleaned).lower()
        if (
            "simulation" not in blob
            and "fat" not in blob
            and "factory acceptance" not in blob
        ):
            cleaned.insert(
                0,
                "Run in simulation or an approved FAT environment — do not test on a live field PLC.",
            )
        return cleaned

    @field_validator("test_steps")
    @classmethod
    def _non_empty_steps(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("test_steps must not be empty")
        return cleaned


# YC dual-model architecture aliases
StrictFindingSchema = ConstrainedFinding
BehavioralFindingSchema = BehavioralFinding
