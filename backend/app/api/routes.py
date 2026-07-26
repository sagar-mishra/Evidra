"""
FastAPI route handlers for the Release Assurance backend.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.ai.llm_generator import LLMGeneratorError, get_default_generator
from app.schemas.review import (
    AnalyzeResponse,
    MockFindingsResponse,
    ReleaseRecommendation,
    build_findings_summary,
)
from app.schemas.tests import GenerateTestRequest, GenerateTestResponse
from app.services.demo_findings import build_yc_demo_findings
from app.services.pipeline import PipelineError, run_analysis_pipeline

router = APIRouter(prefix="/api/v1", tags=["release-assurance"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (no LLM call)."""
    return {"status": "ok", "service": "release-assurance-backend"}


@router.get(
    "/mock-findings",
    response_model=MockFindingsResponse,
    summary="YC demo: 3 curated behavioral findings",
)
def mock_findings() -> MockFindingsResponse:
    """Return the three curated DC1 findings for UI wiring / offline demo."""
    result = build_yc_demo_findings(changes_analyzed=16)
    return MockFindingsResponse(
        items=result["items"],
        count=result["count"],
        summary=result["summary"],
        project=result["project"],
        dataset_type=result.get("dataset_type")
        or "Synthetic controls-release benchmark",
        controller=result["controller"],
        baseline=result["baseline"],
        revised=result["revised"],
        soo=result.get("soo"),
        release_recommendation=result.get("release_recommendation")
        or ReleaseRecommendation(),
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload L5X pair + governing docs and run analysis",
)
async def analyze(
    baseline_l5x: UploadFile = File(..., description="Baseline Studio 5000 L5X export"),
    revised_l5x: UploadFile = File(..., description="Revised Studio 5000 L5X export"),
    governing_docs: List[UploadFile] = File(
        ...,
        description="One or more governing documents (PDF, DOCX, XLSX, CSV)",
    ),
    # Back-compat: single SOO field still accepted if clients send soo_pdf
    soo_pdf: UploadFile | None = File(
        default=None,
        description="Deprecated single SOO upload; prefer governing_docs",
    ),
) -> AnalyzeResponse:
    """
    Accept baseline/revised L5X plus multi-file governing documents.
    YC demo returns 3 curated behavioral findings with real diff counts.
    """
    _validate_upload_name(baseline_l5x, {".l5x", ".xml"}, "baseline_l5x")
    _validate_upload_name(revised_l5x, {".l5x", ".xml"}, "revised_l5x")

    docs = list(governing_docs or [])
    if soo_pdf is not None and (soo_pdf.filename or "").strip():
        docs.append(soo_pdf)
    if not docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one governing document is required (governing_docs).",
        )

    allowed_docs = {".pdf", ".docx", ".xlsx", ".xls", ".csv"}
    for i, doc in enumerate(docs):
        _validate_upload_name(doc, allowed_docs, f"governing_docs[{i}]")

    tmp_dir = Path(tempfile.mkdtemp(prefix="release_assurance_"))
    try:
        baseline_path = await _save_upload(
            baseline_l5x,
            tmp_dir / f"baseline{Path(baseline_l5x.filename or 'b.L5X').suffix}",
        )
        revised_path = await _save_upload(
            revised_l5x,
            tmp_dir / f"revised{Path(revised_l5x.filename or 'r.L5X').suffix}",
        )
        soo_paths: list[Path] = []
        for i, doc in enumerate(docs):
            suffix = Path(doc.filename or f"doc{i}.pdf").suffix
            soo_paths.append(
                await _save_upload(doc, tmp_dir / f"gov_{i}{suffix}")
            )

        try:
            result = run_analysis_pipeline(
                baseline_path,
                revised_path,
                soo_paths,
            )
        except PipelineError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis pipeline failed: {exc}",
            ) from exc

        summary = result.get("summary") or build_findings_summary(
            result["items"],
            changes_analyzed=(result.get("diff_summary") or {}).get("total_changes"),
        )
        return AnalyzeResponse(
            items=result["items"],
            count=result["count"],
            summary=summary,
            source="pipeline",
            project=result["project"],
            dataset_type=result.get("dataset_type")
            or "Synthetic controls-release benchmark",
            controller=result["controller"],
            baseline=result["baseline"],
            revised=result["revised"],
            soo=result.get("soo"),
            governing_docs=result.get("governing_docs"),
            diff_summary=result.get("diff_summary"),
            soo_block_count=result.get("soo_block_count"),
            message=result.get("message")
            or f"Generated {result['count']} review findings.",
            release_recommendation=result.get("release_recommendation"),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post(
    "/generate-test",
    response_model=GenerateTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a schema-validated regression test plan",
)
def generate_test(request: GenerateTestRequest) -> GenerateTestResponse:
    generator = get_default_generator()
    try:
        plan = generator.generate_from_request(request)
    except LLMGeneratorError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return GenerateTestResponse(
        test_plan=plan,
        model=generator.model,
        api_base=generator.api_base or "",
    )


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------


def _validate_upload_name(
    upload: UploadFile,
    allowed_suffixes: set[str],
    field_name: str,
) -> None:
    name = (upload.filename or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}: filename is required",
        )
    suffix = Path(name).suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{field_name}: unsupported file type '{suffix}'. "
                f"Allowed: {sorted(allowed_suffixes)}"
            ),
        )


async def _save_upload(upload: UploadFile, dest: Path) -> Path:
    try:
        content = await upload.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{upload.filename or dest.name}: empty file",
            )
        dest.write_bytes(content)
        return dest
    finally:
        await upload.close()
