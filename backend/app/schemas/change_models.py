"""
Frozen domain models for release-assurance change analysis.

Pydantic v2 schemas used by the deterministic engines (Milestone 2+)
and later by Instructor-enforced AI outputs (Milestone 4+).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChangeClass(str, Enum):
    """Four behavioral change classes used across the pipeline."""

    INTERLOCKS = "Interlocks"
    ALARMS_TIMERS = "Alarms/Timers"
    MODES = "Modes"
    SEQUENCES = "Sequences"


CHANGE_CLASSES: tuple[str, ...] = tuple(c.value for c in ChangeClass)


class DiffOperation(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class DiffArtifactType(str, Enum):
    TAG = "tag"
    RUNG = "rung"
    ROUTINE = "routine"
    PROGRAM = "program"


class NormalizedIdentity(BaseModel):
    """Canonical identity for a PLC tag or equipment reference."""

    raw_name: str
    canonical_name: str
    equipment: str | None = None
    role: str | None = None


class BehavioralChange(BaseModel):
    """One true behavioral difference between baseline and revised L5X."""

    change_id: str
    artifact_type: DiffArtifactType
    operation: DiffOperation
    change_class: ChangeClass
    location: str = Field(
        ...,
        description="Human-readable PLC location, e.g. Controller tag or Program/Routine/Rung",
    )
    tag_name: str | None = None
    canonical_name: str | None = None
    equipment: str | None = None
    baseline: dict[str, Any] | None = None
    revised: dict[str, Any] | None = None
    summary: str


class DiffSummary(BaseModel):
    tag_changes: int = 0
    rung_changes: int = 0
    routine_changes: int = 0
    program_changes: int = 0
    total_changes: int = 0
    by_change_class: dict[str, int] = Field(default_factory=dict)
    by_operation: dict[str, int] = Field(default_factory=dict)


class DiffReport(BaseModel):
    """Full deterministic diff result for a baseline vs revised L5X pair."""

    baseline_source: str
    revised_source: str
    baseline_controller: str | None = None
    revised_controller: str | None = None
    changes: list[BehavioralChange] = Field(default_factory=list)
    summary: DiffSummary = Field(default_factory=DiffSummary)
    ignored_noise_categories: list[str] = Field(
        default_factory=lambda: [
            "ExportDate",
            "ToolID",
            "Owner",
            "ProjectCreationDate",
            "LastModifiedDate",
            "ProjectSN",
            "SoftwareRevision",
            "SchemaRevision",
            "ExportOptions",
            "ContainsContext",
            "whitespace_only_formatting",
        ]
    )
