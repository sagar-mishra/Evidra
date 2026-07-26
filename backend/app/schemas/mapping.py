"""
Pydantic schemas for SOO/FDS requirement extraction and tag mapping.

Used by the hybrid mapping engine (Milestone 3) and later by Instructor-enforced
local LLM extraction (Milestone 4). Never parse raw LLM text without these models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.change_models import ChangeClass


class RequirementPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class RequirementCategory(str, Enum):
    """Aligns loosely with behavioral change classes + common SOO themes."""

    INTERLOCK = "interlock"
    ALARM = "alarm"
    TIMER = "timer"
    MODE = "mode"
    SEQUENCE = "sequence"
    SETPOINT = "setpoint"
    PERMISSIVE = "permissive"
    FAILOVER = "failover"
    GENERAL = "general"


class StructuredRequirement(BaseModel):
    """
    One structured requirement extracted from SOO/FDS text.

    Instructor will force the local LLM to emit this schema only.
    """

    requirement_id: str = Field(
        ...,
        description="Stable ID from the source document when present (e.g. REQ-024).",
        examples=["REQ-024"],
    )
    statement: str = Field(
        ...,
        min_length=1,
        description="Normalized requirement statement in plain English.",
    )
    category: RequirementCategory = Field(
        default=RequirementCategory.GENERAL,
        description="Behavioral category inferred from the requirement language.",
    )
    change_class: ChangeClass | None = Field(
        default=None,
        description="Mapped pipeline change class when determinable.",
    )
    priority: RequirementPriority = Field(default=RequirementPriority.UNKNOWN)
    equipment_mentions: list[str] = Field(
        default_factory=list,
        description="Equipment names/aliases mentioned (e.g. CHWP-01, Pump 101).",
    )
    tag_hints: list[str] = Field(
        default_factory=list,
        description="Explicit PLC tag names if present in the requirement text.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Salient tokens for sparse/BM25 matching.",
    )
    source_block_id: str | None = Field(
        default=None,
        description="Originating text block id from doc_parser (e.g. docx-t4-r2).",
    )
    source_excerpt: str | None = Field(
        default=None,
        description="Verbatim excerpt used as evidence for this requirement.",
    )

    @field_validator("requirement_id")
    @classmethod
    def _strip_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("requirement_id must not be empty")
        return cleaned


class RequirementExtractionResult(BaseModel):
    """Batch result of SOO/FDS requirement extraction."""

    source_file: str
    requirements: list[StructuredRequirement] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.requirements)


class TagIndexRecord(BaseModel):
    """Payload stored in Qdrant for a PLC tag."""

    tag_name: str
    canonical_name: str
    description: str = ""
    data_type: str | None = None
    equipment: str | None = None
    role: str | None = None
    value: str | None = None
    scope: str = "controller"
    program: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def embed_text(self) -> str:
        """
        Text used for dense + sparse embedding.

        Includes name, description, and equipment so exact BM25 hits and
        semantic intent both have signal.
        """
        parts = [
            self.tag_name,
            self.canonical_name,
            self.description or "",
            self.equipment or "",
            self.role or "",
            self.data_type or "",
        ]
        return " | ".join(p for p in parts if p)


class HybridSearchHit(BaseModel):
    """One hybrid-search result (after RRF fusion)."""

    tag_name: str
    canonical_name: str | None = None
    description: str | None = None
    equipment: str | None = None
    score: float
    rank: int
    payload: dict[str, Any] = Field(default_factory=dict)


class HybridSearchResult(BaseModel):
    """Full hybrid search response for a requirement/query string."""

    query: str
    collection: str
    hits: list[HybridSearchHit] = Field(default_factory=list)
    top_tag: str | None = None

    @property
    def best_match(self) -> HybridSearchHit | None:
        return self.hits[0] if self.hits else None


class RequirementTagMapping(BaseModel):
    """Link between a structured requirement and candidate PLC tags."""

    requirement: StructuredRequirement
    candidates: list[HybridSearchHit] = Field(default_factory=list)
    selected_tag: str | None = None
    match_method: str = Field(
        default="hybrid_rrf",
        description="hybrid_rrf | exact_tag | alias | lexical",
    )
    confidence: float | None = None
    evidence: str | None = None


class MappingReport(BaseModel):
    """Aggregate mapping output for a set of requirements vs indexed tags."""

    mappings: list[RequirementTagMapping] = Field(default_factory=list)
    unmapped_requirement_ids: list[str] = Field(default_factory=list)
    indexed_tag_count: int = 0
