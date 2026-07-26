"""
Milestone 6 — Benchmark Validation (end-to-end, backend only).

Orchestrates the full release-assurance pipeline against the DC1 synthetic
benchmark package and scores results against sample_data/ground_truth.json.

Pipeline:
  1. Ingest baseline + revised L5X
  2. Deterministic diff (run twice → reproducibility)
  3. Qdrant hybrid mapping (dense + BM25 + RRF)
  4. Local LLM regression-test generation (LiteLLM + Instructor → Ollama)

Metrics (plan.md targets):
  - End-to-end processing time          < 10 minutes
  - Deterministic L5X diff reproducibility  = 100%
  - AI mapping precision / recall      >= 80%

Usage (from project root):
    uv run python backend/tests/test_benchmark.py

Optional environment:
    LLM_MODEL=ollama/llama3.1
    LLM_API_BASE=http://localhost:11434
    BENCHMARK_SKIP_LLM=1          # skip generation stage (mapping+diff only)
    BENCHMARK_LLM_LIMIT=16        # max findings to generate (default: all revision-caused)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.ai.llm_generator import LLMGeneratorError, RegressionTestGenerator
from app.ai.qdrant_engine import QdrantEngineError, QdrantHybridEngine
from app.schemas.change_models import BehavioralChange, DiffArtifactType, DiffReport
from app.schemas.mapping import TagIndexRecord
from app.schemas.tests import RegressionTestSchema
from app.services.diff_engine import DiffEngineError, diff_l5x_files
from app.services.lxml_parser import L5XParseError, parse_l5x
from app.services.name_normalizer import normalize_identity, normalize_tag_name

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SAMPLE_DIR = (Path(__file__).resolve().parent / ".." / ".." / "sample_data").resolve()
BASELINE_L5X = SAMPLE_DIR / "DC1_Cooling_Baseline_RevA.L5X"
REVISED_L5X = SAMPLE_DIR / "DC1_Cooling_Revised_RevB.L5X"
GROUND_TRUTH = SAMPLE_DIR / "ground_truth.json"
REPORT_PATH = SAMPLE_DIR / "VALIDATION_REPORT.md"

# Targets from plan.md / business requirements
TARGET_E2E_SECONDS = 10 * 60  # < 10 minutes
TARGET_DIFF_REPRO = 1.0  # 100%
TARGET_MAPPING_SCORE = 0.80  # >= 80%
MAPPING_TOP_K = 3

SKIP_LLM = os.getenv("BENCHMARK_SKIP_LLM", "").strip() in {"1", "true", "TRUE", "yes"}
LLM_LIMIT = int(os.getenv("BENCHMARK_LLM_LIMIT", "0") or "0")  # 0 = no limit


# ---------------------------------------------------------------------------
# Ground-truth ↔ engine matching
# ---------------------------------------------------------------------------

# Revision-caused findings that the L5X diff engine is expected to surface.
# GT-015 / GT-016 are pre-existing / missing-implementation (not L5X diffs).
GT_DIFF_MATCHERS: list[tuple[str, Callable[[BehavioralChange], bool]]] = [
    ("GT-001", lambda c: c.tag_name == "CFG_CHW_DP_SP"),
    ("GT-002", lambda c: c.tag_name == "CFG_PumpFlowProofTimeout_ms"),
    ("GT-003", lambda c: c.tag_name == "CFG_SAT_High_SP"),
    (
        "GT-004",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R30_CHWP_Control" in c.location
        and c.location.endswith("rung:5"),
    ),
    (
        "GT-005",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R40_AHU_Control" in c.location
        and c.location.endswith("rung:3"),
    ),
    ("GT-006", lambda c: c.tag_name == "CFG_CHW_SuctionLowTrip_SP"),
    (
        "GT-007",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R30_CHWP_Control" in c.location
        and c.location.endswith("rung:9"),
    ),
    (
        "GT-008",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R40_AHU_Control" in c.location
        and c.location.endswith("rung:6"),
    ),
    (
        "GT-009",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R50_Alarms" in c.location
        and (c.location.endswith("rung:13") or c.location.endswith("rung:15")),
    ),
    ("GT-010", lambda c: c.tag_name == "CFG_CHW_DP_LowAlarm_SP"),
    ("GT-011", lambda c: c.tag_name == "CFG_LeadRotation_hr"),
    (
        "GT-012",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R40_AHU_Control" in c.location
        and c.location.endswith("rung:5"),
    ),
    ("GT-013", lambda c: c.tag_name == "CFG_PumpPostRun_ms"),
    (
        "GT-014",
        lambda c: c.artifact_type == DiffArtifactType.RUNG
        and "R30_CHWP_Control" in c.location
        and (c.location.endswith("rung:2") or c.location.endswith("rung:3")),
    ),
]

# Expected primary PLC tags for hybrid mapping evaluation (per finding).
GT_MAPPING_TARGETS: dict[str, list[str]] = {
    "GT-001": ["CFG_CHW_DP_SP"],
    "GT-002": ["CFG_PumpFlowProofTimeout_ms"],
    "GT-003": ["CFG_SAT_High_SP"],
    "GT-004": ["CHWP02_Permissive", "DI_LeakDetected"],
    "GT-005": ["AHU02_Permissive", "DI_FireAlarm_Active"],
    "GT-006": ["CFG_CHW_SuctionLowTrip_SP"],
    "GT-007": ["TMR_CHWP02_FlowProof", "CFG_PumpFlowProofTimeout_ms", "ALM_CHWP02_FailToStart"],
    "GT-008": ["TMR_AHU01_AirflowProof", "CFG_AHU_AirflowProofTimeout_ms", "ALM_AHU01_FailToStart"],
    "GT-009": ["CFG_SAT_HighHigh_Delay_ms", "TMR_AHU01_SAT_HighHigh", "TMR_AHU02_SAT_HighHigh"],
    "GT-010": ["CFG_CHW_DP_LowAlarm_SP"],
    "GT-011": ["CFG_LeadRotation_hr"],
    "GT-012": ["HMI_AHU02_HandCmd", "HMI_AHU01_HandCmd", "CMD_AHU02_Start"],
    "GT-013": ["CFG_PumpPostRun_ms"],
    "GT-014": ["CHWP02_FailoverRequest", "CHWP01_FailoverRequest"],
    "GT-015": ["CFG_CHW_ReturnHigh_SP"],
    "GT-016": ["ALM_AHU02_FilterDirty", "DI_AHU02_FilterDirty", "RAW_DI_AHU02_FilterDirty"],
}

OUT_OF_SCOPE_DIFF_GT = {"GT-015", "GT-016"}


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass
class StageTiming:
    name: str
    seconds: float


@dataclass
class MappingEvalRow:
    finding_id: str
    query: str
    expected_tags: list[str]
    top_tags: list[str]
    hit_at_1: bool
    hit_at_k: bool


@dataclass
class GenerationEvalRow:
    finding_id: str
    change_id: str
    success: bool
    test_id: str | None = None
    keyword_overlap: float | None = None
    error: str | None = None


@dataclass
class BenchmarkResult:
    started_at: str
    finished_at: str = ""
    e2e_seconds: float = 0.0
    stage_timings: list[StageTiming] = field(default_factory=list)

    # Ingest
    baseline_tags: int = 0
    revised_tags: int = 0
    baseline_rungs: int = 0
    revised_rungs: int = 0

    # Diff
    diff_change_count: int = 0
    diff_tag_changes: int = 0
    diff_rung_changes: int = 0
    diff_repro_score: float = 0.0
    diff_gt_detected: list[str] = field(default_factory=list)
    diff_gt_missed: list[str] = field(default_factory=list)
    diff_detection_recall: float = 0.0

    # Mapping
    mapping_rows: list[MappingEvalRow] = field(default_factory=list)
    mapping_precision_at_1: float = 0.0
    mapping_recall_at_k: float = 0.0
    mapping_f1: float = 0.0

    # Generation
    generation_rows: list[GenerationEvalRow] = field(default_factory=list)
    generation_success_rate: float = 0.0
    generation_skipped: bool = False

    # Gates
    pass_e2e_time: bool = False
    pass_diff_repro: bool = False
    pass_mapping: bool = False
    overall_pass: bool = False
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _divider(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _change_fingerprint(change: BehavioralChange) -> str:
    payload = {
        "artifact_type": change.artifact_type.value,
        "operation": change.operation.value,
        "location": change.location,
        "tag_name": change.tag_name,
        "baseline": change.baseline,
        "revised": change.revised,
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _report_fingerprint(report: DiffReport) -> list[str]:
    return sorted(_change_fingerprint(c) for c in report.changes)


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


def _extract_req_ids(text: str) -> list[str]:
    return re.findall(r"REQ-\d+", text.upper())


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _keyword_overlap(expected: str, actual: str) -> float:
    a = _tokenize(expected)
    b = _tokenize(actual)
    if not a:
        return 0.0
    return _safe_div(len(a & b), len(a))


def _build_mapping_query(finding: dict[str, Any]) -> str:
    parts = [
        finding.get("Governing Source", ""),
        finding.get("Category", ""),
        finding.get("Baseline Evidence", ""),
        finding.get("Revised Evidence", ""),
        finding.get("Expected Prototype Result", ""),
    ]
    return " | ".join(p for p in parts if p)


def _change_to_tag_change_text(change: BehavioralChange) -> str:
    if change.artifact_type == DiffArtifactType.TAG:
        b = (change.baseline or {}).get("value")
        r = (change.revised or {}).get("value")
        return f"{change.tag_name} changed from {b!s} to {r!s} at {change.location}"
    b = (change.baseline or {}).get("text") or (change.baseline or {}).get("normalized_text")
    r = (change.revised or {}).get("text") or (change.revised or {}).get("normalized_text")
    return (
        f"Logic change at {change.location}: "
        f"baseline={b!s} revised={r!s}"
    )


def _match_gt_ids(change: BehavioralChange) -> list[str]:
    return [gt_id for gt_id, pred in GT_DIFF_MATCHERS if pred(change)]


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def stage_ingest() -> tuple[dict[str, Any], dict[str, Any], float]:
    t0 = time.perf_counter()
    baseline = parse_l5x(BASELINE_L5X)
    revised = parse_l5x(REVISED_L5X)
    return baseline, revised, time.perf_counter() - t0


def stage_diff() -> tuple[DiffReport, DiffReport, float, float]:
    """Run diff twice; return both reports, stage time, and reproducibility score."""
    t0 = time.perf_counter()
    report_a = diff_l5x_files(BASELINE_L5X, REVISED_L5X)
    report_b = diff_l5x_files(BASELINE_L5X, REVISED_L5X)
    elapsed = time.perf_counter() - t0

    fp_a = _report_fingerprint(report_a)
    fp_b = _report_fingerprint(report_b)
    if not fp_a and not fp_b:
        repro = 1.0
    else:
        # Fraction of identical fingerprints (Jaccard on ordered equality → exact set match)
        repro = 1.0 if fp_a == fp_b else _safe_div(len(set(fp_a) & set(fp_b)), len(set(fp_a) | set(fp_b)))
    return report_a, report_b, elapsed, repro


def stage_mapping(
    revised: dict[str, Any],
    findings: list[dict[str, Any]],
) -> tuple[list[MappingEvalRow], float, float, float, float]:
    """
    Index revised L5X tags into local Qdrant and score hybrid search against GT.

    Precision@1: fraction of queries whose top hit is an expected tag.
    Recall@K: fraction of queries with any expected tag in top-K.

    Returns (rows, precision@1, recall@k, f1, elapsed_seconds).
    """
    t0 = time.perf_counter()
    # Prefer settings (OpenAI dense by default). Fall back to local dense if no API key
    # so the benchmark remains runnable offline for mapping-stage validation.
    from app.core.config import settings as _settings

    emb_provider = _settings.EMBEDDING_PROVIDER
    if emb_provider == "openai" and not (_settings.OPENAI_API_KEY or "").strip():
        print("  NOTE: OPENAI_API_KEY unset — using local dense embeddings for mapping stage.")
        emb_provider = "local"

    engine = QdrantHybridEngine(
        collection_name="benchmark_plc_tags",
        recreate_collection=True,
        embedding_provider=emb_provider,
        in_memory=True,
    )

    records: list[TagIndexRecord] = []
    for name, tag in revised.get("tags", {}).items():
        identity = normalize_identity(tag.get("name") or name)
        records.append(
            TagIndexRecord(
                tag_name=tag.get("name") or name,
                canonical_name=identity.canonical_name,
                description=tag.get("description") or "",
                data_type=tag.get("data_type"),
                equipment=identity.equipment,
                role=identity.role,
                value=str(tag["value"]) if tag.get("value") is not None else None,
                scope=tag.get("scope") or "controller",
            )
        )
    engine.index_tags(records)

    rows: list[MappingEvalRow] = []
    # Evaluate mapping on all findings that have target tags defined
    for finding in findings:
        fid = finding["Finding ID"]
        expected = GT_MAPPING_TARGETS.get(fid, [])
        if not expected:
            continue
        # For missing tags (GT-016), still run query — may correctly rank nearest related AHU02 tags
        query = _build_mapping_query(finding)
        try:
            result = engine.hybrid_search(query, limit=MAPPING_TOP_K)
            top_tags = [h.tag_name for h in result.hits]
        except QdrantEngineError as exc:
            print(f"  WARNING: hybrid_search failed for {fid}: {exc}")
            top_tags = []

        expected_norm = {normalize_tag_name(t) for t in expected}
        top_norm = [normalize_tag_name(t) for t in top_tags]
        hit_at_1 = bool(top_norm) and top_norm[0] in expected_norm
        hit_at_k = any(t in expected_norm for t in top_norm)
        rows.append(
            MappingEvalRow(
                finding_id=fid,
                query=query[:200],
                expected_tags=expected,
                top_tags=top_tags,
                hit_at_1=hit_at_1,
                hit_at_k=hit_at_k,
            )
        )

    elapsed = time.perf_counter() - t0
    precision = _safe_div(sum(1 for r in rows if r.hit_at_1), len(rows))
    recall = _safe_div(sum(1 for r in rows if r.hit_at_k), len(rows))
    f1 = (
        _safe_div(2 * precision * recall, precision + recall)
        if (precision + recall)
        else 0.0
    )
    return rows, precision, recall, f1, elapsed


def stage_generation(
    report: DiffReport,
    findings_by_id: dict[str, dict[str, Any]],
) -> tuple[list[GenerationEvalRow], float, float]:
    """Generate schema-validated tests for each revision-caused change via local LLM."""
    if SKIP_LLM:
        return [], 0.0, 0.0

    t0 = time.perf_counter()
    generator = RegressionTestGenerator()
    rows: list[GenerationEvalRow] = []

    # Pair each change with its GT finding(s)
    work: list[tuple[BehavioralChange, str]] = []
    for change in report.changes:
        gt_ids = _match_gt_ids(change)
        if not gt_ids:
            # Still generate for unmatched diffs using location as requirement proxy
            work.append((change, ""))
        else:
            for gid in gt_ids:
                work.append((change, gid))

    # Deduplicate by (change_id, gt_id)
    seen: set[tuple[str, str]] = set()
    unique_work: list[tuple[BehavioralChange, str]] = []
    for change, gid in work:
        key = (change.change_id, gid)
        if key in seen:
            continue
        seen.add(key)
        unique_work.append((change, gid))

    if LLM_LIMIT > 0:
        unique_work = unique_work[:LLM_LIMIT]

    print(f"  Generating {len(unique_work)} regression test plan(s) via {generator.model} ...")

    for change, gid in unique_work:
        finding = findings_by_id.get(gid, {})
        requirement = (
            finding.get("Governing Source")
            or finding.get("Expected Regression Test")
            or f"Verify behavioral change at {change.location}"
        )
        expected_test = finding.get("Expected Regression Test", "")
        tag_change = _change_to_tag_change_text(change)
        related = [change.tag_name] if change.tag_name else []
        equipment = [change.equipment] if change.equipment else None

        try:
            plan: RegressionTestSchema = generator.generate_regression_test(
                tag_change=tag_change,
                requirement=str(requirement),
                affected_equipment=equipment,
                related_tags=related or None,
            )
            # Soft relevance: overlap of generated text with expected GT regression language
            generated_blob = " ".join(
                [
                    plan.title,
                    plan.purpose,
                    plan.expected_result,
                    " ".join(plan.prerequisites),
                    " ".join(s.action for s in plan.test_steps),
                ]
            )
            overlap = _keyword_overlap(expected_test, generated_blob) if expected_test else None
            rows.append(
                GenerationEvalRow(
                    finding_id=gid or "UNMAPPED",
                    change_id=change.change_id,
                    success=True,
                    test_id=plan.test_id,
                    keyword_overlap=overlap,
                )
            )
            print(f"    OK  {change.change_id} / {gid or '-'} → {plan.test_id}")
        except LLMGeneratorError as exc:
            rows.append(
                GenerationEvalRow(
                    finding_id=gid or "UNMAPPED",
                    change_id=change.change_id,
                    success=False,
                    error=str(exc)[:300],
                )
            )
            print(f"    FAIL {change.change_id} / {gid or '-'}: {exc}")

    elapsed = time.perf_counter() - t0
    success_rate = _safe_div(sum(1 for r in rows if r.success), len(rows))
    return rows, success_rate, elapsed


# ---------------------------------------------------------------------------
# Scoring + report
# ---------------------------------------------------------------------------


def score_diff_against_gt(
    report: DiffReport,
) -> tuple[list[str], list[str], float]:
    expected_ids = [gid for gid, _ in GT_DIFF_MATCHERS]
    # Unique expected finding IDs
    expected_unique = sorted(set(expected_ids))
    detected: set[str] = set()
    for change in report.changes:
        detected.update(_match_gt_ids(change))
    missed = [gid for gid in expected_unique if gid not in detected]
    found = sorted(detected)
    recall = _safe_div(len(found), len(expected_unique))
    return found, missed, recall


def write_markdown_report(result: BenchmarkResult, ground_truth: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# DC1 Release Assurance — Pipeline Benchmark Report")
    lines.append("")
    lines.append(f"**Generated:** {result.finished_at}")
    lines.append(f"**Package:** `{SAMPLE_DIR.name}` synthetic benchmark")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    status = "PASS" if result.overall_pass else "FAIL"
    lines.append(f"**{status}** — automated end-to-end pipeline evaluation.")
    lines.append("")
    lines.append("| Gate | Target | Actual | Status |")
    lines.append("|------|--------|--------|--------|")
    lines.append(
        f"| End-to-end time | < {TARGET_E2E_SECONDS/60:.0f} min "
        f"| {result.e2e_seconds:.1f} s ({result.e2e_seconds/60:.2f} min) "
        f"| {'PASS' if result.pass_e2e_time else 'FAIL'} |"
    )
    lines.append(
        f"| Deterministic L5X diff reproducibility | 100% "
        f"| {result.diff_repro_score*100:.1f}% "
        f"| {'PASS' if result.pass_diff_repro else 'FAIL'} |"
    )
    lines.append(
        f"| AI mapping precision@1 | ≥ {TARGET_MAPPING_SCORE*100:.0f}% "
        f"| {result.mapping_precision_at_1*100:.1f}% "
        f"| {'PASS' if result.mapping_precision_at_1 >= TARGET_MAPPING_SCORE else 'FAIL'} |"
    )
    lines.append(
        f"| AI mapping recall@{MAPPING_TOP_K} | ≥ {TARGET_MAPPING_SCORE*100:.0f}% "
        f"| {result.mapping_recall_at_k*100:.1f}% "
        f"| {'PASS' if result.mapping_recall_at_k >= TARGET_MAPPING_SCORE else 'FAIL'} |"
    )
    lines.append("")

    lines.append("## Pipeline stages")
    lines.append("")
    lines.append("| Stage | Duration (s) |")
    lines.append("|-------|-------------:|")
    for st in result.stage_timings:
        lines.append(f"| {st.name} | {st.seconds:.2f} |")
    lines.append(f"| **Total** | **{result.e2e_seconds:.2f}** |")
    lines.append("")

    lines.append("## Ingestion")
    lines.append("")
    lines.append(f"- Baseline tags: **{result.baseline_tags}** · rungs: **{result.baseline_rungs}**")
    lines.append(f"- Revised tags: **{result.revised_tags}** · rungs: **{result.revised_rungs}**")
    lines.append("")

    lines.append("## Deterministic diff")
    lines.append("")
    lines.append(f"- Behavioral changes detected: **{result.diff_change_count}** "
                 f"({result.diff_tag_changes} tags, {result.diff_rung_changes} rungs)")
    lines.append(f"- Dual-run reproducibility: **{result.diff_repro_score*100:.1f}%**")
    lines.append(
        f"- Revision-caused GT detection recall: **{result.diff_detection_recall*100:.1f}%** "
        f"({len(result.diff_gt_detected)}/{len(result.diff_gt_detected)+len(result.diff_gt_missed)})"
    )
    lines.append(f"- Detected findings: {', '.join(result.diff_gt_detected) or '—'}")
    lines.append(f"- Missed findings: {', '.join(result.diff_gt_missed) or '—'}")
    lines.append(
        f"- Out-of-scope for L5X-only diff (pre-existing / missing impl.): "
        f"{', '.join(sorted(OUT_OF_SCOPE_DIFF_GT))}"
    )
    lines.append("")

    lines.append("## Hybrid mapping (Qdrant dense + BM25 + RRF)")
    lines.append("")
    lines.append(f"- Precision@1: **{result.mapping_precision_at_1*100:.1f}%**")
    lines.append(f"- Recall@{MAPPING_TOP_K}: **{result.mapping_recall_at_k*100:.1f}%**")
    lines.append(f"- F1: **{result.mapping_f1*100:.1f}%**")
    lines.append("")
    lines.append("| Finding | Hit@1 | Hit@K | Top tags | Expected |")
    lines.append("|---------|------:|------:|----------|----------|")
    for row in result.mapping_rows:
        lines.append(
            f"| {row.finding_id} "
            f"| {'Y' if row.hit_at_1 else 'N'} "
            f"| {'Y' if row.hit_at_k else 'N'} "
            f"| {', '.join(row.top_tags[:3]) or '—'} "
            f"| {', '.join(row.expected_tags)} |"
        )
    lines.append("")

    lines.append("## AI test generation (LiteLLM + Instructor → local Ollama)")
    lines.append("")
    if result.generation_skipped:
        lines.append("- **Skipped** (`BENCHMARK_SKIP_LLM=1`).")
    else:
        lines.append(f"- Schema-valid success rate: **{result.generation_success_rate*100:.1f}%**")
        ok = sum(1 for r in result.generation_rows if r.success)
        lines.append(f"- Generated plans: **{ok}/{len(result.generation_rows)}**")
        overlaps = [r.keyword_overlap for r in result.generation_rows if r.keyword_overlap is not None]
        if overlaps:
            avg_ov = sum(overlaps) / len(overlaps)
            lines.append(f"- Mean keyword overlap vs GT expected tests: **{avg_ov*100:.1f}%** (soft metric)")
        lines.append("")
        lines.append("| Finding | Change | Success | Test ID | Overlap |")
        lines.append("|---------|--------|:-------:|---------|--------:|")
        for row in result.generation_rows:
            ov = f"{row.keyword_overlap*100:.0f}%" if row.keyword_overlap is not None else "—"
            lines.append(
                f"| {row.finding_id} | {row.change_id} "
                f"| {'Y' if row.success else 'N'} "
                f"| {row.test_id or '—'} | {ov} |"
            )
    lines.append("")

    lines.append("## Ground truth package reference")
    lines.append("")
    n_findings = len(ground_truth.get("findings", []))
    n_tests = len(ground_truth.get("regression_tests", []))
    lines.append(f"- Findings in `ground_truth.json`: **{n_findings}**")
    lines.append(f"- Regression tests in `ground_truth.json`: **{n_tests}**")
    lines.append("- Change surface expectation: 7 tag values + 9 ladder rungs (VALIDATION package).")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    if result.notes:
        for note in result.notes:
            lines.append(f"- {note}")
    else:
        lines.append("- No additional notes.")
    lines.append("")
    lines.append("## Hold point")
    lines.append("")
    lines.append(
        "This report evaluates the **read-only release-assurance prototype** only. "
        "It does **not** approve a controller download, FAT, or production release. "
        "A qualified controls engineer must explicitly accept or reject each finding."
    )
    lines.append("")
    lines.append("---")
    lines.append("*Generated by `backend/tests/test_benchmark.py` (Milestone 6).*")
    lines.append("")

    text = "\n".join(lines)
    REPORT_PATH.write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("Milestone 6 — Benchmark Validation (end-to-end pipeline)")
    print(f"Sample dir : {SAMPLE_DIR.as_posix()}")
    print(f"Ground truth: {GROUND_TRUTH.as_posix()}")
    print(f"Report out : {REPORT_PATH.as_posix()}")
    print(f"Skip LLM   : {SKIP_LLM}")

    missing = [p for p in (BASELINE_L5X, REVISED_L5X, GROUND_TRUTH) if not p.is_file()]
    if missing:
        print("ERROR: missing required files:", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 1

    ground_truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    findings: list[dict[str, Any]] = ground_truth.get("findings", [])
    findings_by_id = {f["Finding ID"]: f for f in findings}

    result = BenchmarkResult(
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    wall0 = time.perf_counter()

    try:
        # ---- 1. Ingest ----
        _divider("STAGE 1 — L5X Ingestion")
        baseline, revised, t_ingest = stage_ingest()
        result.stage_timings.append(StageTiming("ingest", t_ingest))
        result.baseline_tags = baseline["summary"]["tag_count"]
        result.revised_tags = revised["summary"]["tag_count"]
        result.baseline_rungs = baseline["summary"]["rung_count"]
        result.revised_rungs = revised["summary"]["rung_count"]
        print(
            f"Baseline: {result.baseline_tags} tags / {result.baseline_rungs} rungs | "
            f"Revised: {result.revised_tags} tags / {result.revised_rungs} rungs "
            f"({t_ingest:.2f}s)"
        )

        # ---- 2. Diff + reproducibility ----
        _divider("STAGE 2 — Deterministic Diff (×2 for reproducibility)")
        report_a, _report_b, t_diff, repro = stage_diff()
        result.stage_timings.append(StageTiming("diff_dual_run", t_diff))
        result.diff_change_count = report_a.summary.total_changes
        result.diff_tag_changes = report_a.summary.tag_changes
        result.diff_rung_changes = report_a.summary.rung_changes
        result.diff_repro_score = repro
        detected, missed, det_recall = score_diff_against_gt(report_a)
        result.diff_gt_detected = detected
        result.diff_gt_missed = missed
        result.diff_detection_recall = det_recall
        print(
            f"Changes: {result.diff_change_count} "
            f"(tags={result.diff_tag_changes}, rungs={result.diff_rung_changes})"
        )
        print(f"Reproducibility: {repro*100:.1f}%")
        print(f"GT detection recall: {det_recall*100:.1f}%  found={detected}  missed={missed}")

        # ---- 3. Mapping ----
        _divider("STAGE 3 — Qdrant Hybrid Mapping")
        map_rows, precision, recall, f1, t_map = stage_mapping(revised, findings)
        # stage_mapping returns 5 values - fix the unpacking (I had a bug with type ignore)
        result.stage_timings.append(StageTiming("mapping_qdrant", t_map))
        result.mapping_rows = map_rows
        result.mapping_precision_at_1 = precision
        result.mapping_recall_at_k = recall
        result.mapping_f1 = f1
        print(f"Precision@1={precision*100:.1f}%  Recall@{MAPPING_TOP_K}={recall*100:.1f}%  F1={f1*100:.1f}%")
        for row in map_rows:
            mark = "✓" if row.hit_at_k else "✗"
            print(f"  {mark} {row.finding_id}: top={row.top_tags[:2]} expected={row.expected_tags[:2]}")

        # ---- 4. Generation ----
        _divider("STAGE 4 — LLM Test Generation")
        if SKIP_LLM:
            result.generation_skipped = True
            result.notes.append("LLM generation skipped via BENCHMARK_SKIP_LLM=1.")
            print("Skipped (BENCHMARK_SKIP_LLM=1).")
        else:
            gen_rows, gen_rate, t_gen = stage_generation(report_a, findings_by_id)
            result.stage_timings.append(StageTiming("llm_generation", t_gen))
            result.generation_rows = gen_rows
            result.generation_success_rate = gen_rate
            print(f"Generation success rate: {gen_rate*100:.1f}% ({t_gen:.1f}s)")

    except (L5XParseError, DiffEngineError, QdrantEngineError) as exc:
        print(f"FATAL pipeline error: {exc}", file=sys.stderr)
        traceback.print_exc()
        result.notes.append(f"Pipeline aborted: {exc}")
        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.e2e_seconds = time.perf_counter() - wall0
        write_markdown_report(result, ground_truth)
        return 1
    except Exception as exc:  # noqa: BLE001 — benchmark must always write a report
        print(f"FATAL unexpected error: {exc}", file=sys.stderr)
        traceback.print_exc()
        result.notes.append(f"Unexpected error: {exc}")
        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.e2e_seconds = time.perf_counter() - wall0
        write_markdown_report(result, ground_truth)
        return 1

    # ---- Gates ----
    result.e2e_seconds = time.perf_counter() - wall0
    result.finished_at = datetime.now(timezone.utc).isoformat()
    result.pass_e2e_time = result.e2e_seconds < TARGET_E2E_SECONDS
    result.pass_diff_repro = result.diff_repro_score >= TARGET_DIFF_REPRO
    result.pass_mapping = (
        result.mapping_precision_at_1 >= TARGET_MAPPING_SCORE
        and result.mapping_recall_at_k >= TARGET_MAPPING_SCORE
    )
    # Overall: hard gates on time, repro, mapping. Generation is reported but
    # does not fail the package if Ollama is unavailable when SKIP is not set —
    # if generation ran, require at least 50% schema success to avoid silent empty runs.
    gen_ok = True
    if not result.generation_skipped and result.generation_rows:
        gen_ok = result.generation_success_rate >= 0.5
        if not gen_ok:
            result.notes.append(
                "LLM generation success rate below 50% — check Ollama model availability."
            )
    elif not result.generation_skipped and not result.generation_rows:
        gen_ok = False
        result.notes.append("LLM generation produced zero plans.")

    result.overall_pass = (
        result.pass_e2e_time
        and result.pass_diff_repro
        and result.pass_mapping
        and gen_ok
    )

    if result.diff_change_count != 16:
        result.notes.append(
            f"Expected 16 behavioral diffs (7 tags + 9 rungs); observed {result.diff_change_count}."
        )
    if result.diff_gt_missed:
        result.notes.append(
            f"Diff engine did not surface GT findings: {', '.join(result.diff_gt_missed)}."
        )

    report_text = write_markdown_report(result, ground_truth)

    _divider("BENCHMARK SUMMARY")
    summary = {
        "status": "PASS" if result.overall_pass else "FAIL",
        "e2e_seconds": round(result.e2e_seconds, 2),
        "e2e_minutes": round(result.e2e_seconds / 60.0, 3),
        "diff_reproducibility": round(result.diff_repro_score, 4),
        "diff_changes": result.diff_change_count,
        "diff_gt_detection_recall": round(result.diff_detection_recall, 4),
        "mapping_precision_at_1": round(result.mapping_precision_at_1, 4),
        "mapping_recall_at_k": round(result.mapping_recall_at_k, 4),
        "mapping_f1": round(result.mapping_f1, 4),
        "generation_success_rate": round(result.generation_success_rate, 4),
        "generation_skipped": result.generation_skipped,
        "gates": {
            "e2e_time": result.pass_e2e_time,
            "diff_repro": result.pass_diff_repro,
            "mapping": result.pass_mapping,
            "generation": gen_ok,
        },
        "report": REPORT_PATH.as_posix(),
    }
    print(json.dumps(summary, indent=2))
    print(f"\nMarkdown report written to: {REPORT_PATH.as_posix()}")
    print("\n--- Report preview (first 40 lines) ---")
    for line in report_text.splitlines()[:40]:
        print(line)

    if result.overall_pass:
        print("\nMilestone 6 benchmark PASSED.")
        return 0
    print("\nMilestone 6 benchmark FAILED — see report for details.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    # Fix stage_mapping return annotation usage — ensure 5-tuple unpack works
    raise SystemExit(main())
