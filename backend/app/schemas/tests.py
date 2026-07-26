"""
Pydantic schemas for AI-generated regression test plans.

All LLM outputs for test generation MUST validate against these models
via Instructor — never parse free-form LLM text.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.change_models import ChangeClass


class TestCategory(str, Enum):
    """Category of the proposed regression test."""

    INTERLOCK = "Interlocks"
    ALARMS_TIMERS = "Alarms/Timers"
    MODES = "Modes"
    SEQUENCES = "Sequences"
    SETPOINT = "Setpoint"
    GENERAL = "General"


class TestStep(BaseModel):
    """One ordered action in a regression test procedure."""

    step_number: int = Field(..., ge=1, description="1-based step order.")
    action: str = Field(
        ...,
        min_length=1,
        description="What the tester does (force input, command equipment, wait, etc.).",
    )
    observation: str | None = Field(
        default=None,
        description="Optional intermediate observation for this step.",
    )


class RegressionTestSchema(BaseModel):
    """
    Strict schema for a single focused regression test plan.

    Produced by the local LLM through Instructor + LiteLLM.
    """

    test_id: str = Field(
        ...,
        description="Short identifier for the test case (e.g. TC-F2S-P101).",
        examples=["TC-F2S-P101"],
    )
    title: str = Field(
        ...,
        min_length=1,
        description="Human-readable test title.",
    )
    affected_equipment: list[str] = Field(
        ...,
        min_length=1,
        description="Equipment under test (e.g. PUMP101, CHWP-01, AHU-02).",
    )
    category: TestCategory = Field(
        ...,
        description="Behavioral category of the regression test.",
    )
    change_class: ChangeClass | None = Field(
        default=None,
        description="Pipeline change class when known.",
    )
    related_tags: list[str] = Field(
        default_factory=list,
        description="PLC tags referenced by the test.",
    )
    governing_requirement: str = Field(
        ...,
        min_length=1,
        description="SOO/FDS requirement text or ID that governs this test.",
    )
    change_summary: str = Field(
        ...,
        min_length=1,
        description="What changed in the PLC revision that motivates this test.",
    )
    purpose: str = Field(
        ...,
        min_length=1,
        description="Why this regression test is required.",
    )
    prerequisites: list[str] = Field(
        ...,
        min_length=1,
        description="Preconditions that must be true before executing steps.",
    )
    test_steps: list[TestStep] = Field(
        ...,
        min_length=1,
        description="Ordered test procedure steps.",
    )
    expected_result: str = Field(
        ...,
        min_length=1,
        description="Pass criteria / expected process and PLC behavior.",
    )
    flag_rationale: str = Field(
        ...,
        min_length=1,
        description=(
            "2–4 sentence explainability narrative connecting the PLC change, "
            "mapped engineering requirement, possible operational impact, and "
            "why this regression test is proposed."
        ),
    )
    evidence_to_capture: list[str] = Field(
        default_factory=list,
        description="Trends, watches, or screenshots to capture as FAT evidence.",
    )
    safety_notes: list[str] = Field(
        default_factory=list,
        description="Safety / process cautions for the tester. Advisory only.",
    )

    @field_validator("affected_equipment", "prerequisites")
    @classmethod
    def _non_empty_strings(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("list must contain at least one non-empty string")
        return cleaned

    @field_validator("test_steps")
    @classmethod
    def _ordered_steps(cls, steps: list[TestStep]) -> list[TestStep]:
        if not steps:
            raise ValueError("test_steps must not be empty")
        # Normalize step numbers to 1..N for stable output
        for index, step in enumerate(steps, start=1):
            step.step_number = index
        return steps


class GenerateTestRequest(BaseModel):
    """API request body for POST /api/v1/generate-test."""

    tag_change: str = Field(
        ...,
        min_length=1,
        description="Description of the PLC tag/logic change (baseline → revised).",
        examples=["T_F2S_P101 changed from 10000 to 30000"],
    )
    requirement: str = Field(
        ...,
        min_length=1,
        description="Governing requirement text from SOO/FDS.",
        examples=["Pump 101 fail-to-start timeout"],
    )
    affected_equipment: list[str] | None = Field(
        default=None,
        description="Optional equipment hints to bias generation.",
    )
    related_tags: list[str] | None = Field(
        default=None,
        description="Optional PLC tag names involved in the change.",
    )
    category_hint: TestCategory | None = Field(
        default=None,
        description="Optional category hint from the deterministic diff engine.",
    )


class GenerateTestResponse(BaseModel):
    """API response wrapping a validated regression test plan."""

    test_plan: RegressionTestSchema
    model: str
    api_base: str
