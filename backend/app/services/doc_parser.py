"""
SOO / FDS document text extraction (PDF and DOCX).

Deterministic only — pdfplumber + python-docx. No AI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document


class DocumentParseError(ValueError):
    """Raised when a SOO/FDS document cannot be read or is an unsupported type."""


SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx"})


def parse_document(path: str | Path) -> dict[str, Any]:
    """
    Extract clean text blocks from a SOO/FDS PDF or DOCX file.

    Returns
    -------
    dict with keys:
        source_file, format, page_count (PDF) or paragraph_count (DOCX),
        block_count, text_blocks
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise DocumentParseError(f"Document not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError(
            f"Unsupported document type '{suffix}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if suffix == ".pdf":
        return _parse_pdf(file_path)
    return _parse_docx(file_path)


def extract_text_blocks(path: str | Path) -> list[dict[str, Any]]:
    """Convenience wrapper returning only the list of text blocks."""
    return parse_document(path)["text_blocks"]


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _parse_pdf(file_path: Path) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    page_count = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for page_index, page in enumerate(pdf.pages, start=1):
                raw = page.extract_text() or ""
                for para_index, paragraph in enumerate(
                    _split_paragraphs(raw), start=1
                ):
                    blocks.append(
                        {
                            "block_id": f"pdf-p{page_index}-b{para_index}",
                            "source_type": "pdf",
                            "page": page_index,
                            "index": para_index,
                            "text": paragraph,
                        }
                    )
    except Exception as exc:  # pdfplumber raises varied errors on corrupt files
        raise DocumentParseError(f"Failed to parse PDF {file_path}: {exc}") from exc

    return {
        "source_file": str(file_path).replace("\\", "/"),
        "format": "pdf",
        "page_count": page_count,
        "block_count": len(blocks),
        "text_blocks": blocks,
    }


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------


def _parse_docx(file_path: Path) -> dict[str, Any]:
    try:
        document = Document(str(file_path))
    except Exception as exc:
        raise DocumentParseError(f"Failed to parse DOCX {file_path}: {exc}") from exc

    blocks: list[dict[str, Any]] = []
    para_index = 0
    for paragraph in document.paragraphs:
        text = _normalize_whitespace(paragraph.text)
        if not text:
            continue
        para_index += 1
        style_name = paragraph.style.name if paragraph.style is not None else None
        blocks.append(
            {
                "block_id": f"docx-p{para_index}",
                "source_type": "docx",
                "page": None,
                "index": para_index,
                "style": style_name,
                "text": text,
            }
        )

    # Tables often hold requirements / matrices — extract cell text as blocks.
    for table_index, table in enumerate(document.tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            cell_texts = [
                _normalize_whitespace(cell.text)
                for cell in row.cells
                if _normalize_whitespace(cell.text)
            ]
            if not cell_texts:
                continue
            para_index += 1
            blocks.append(
                {
                    "block_id": f"docx-t{table_index}-r{row_index}",
                    "source_type": "docx_table",
                    "page": None,
                    "index": para_index,
                    "style": f"table_{table_index}",
                    "text": " | ".join(cell_texts),
                }
            )

    return {
        "source_file": str(file_path).replace("\\", "/"),
        "format": "docx",
        "paragraph_count": para_index,
        "block_count": len(blocks),
        "text_blocks": blocks,
    }


# ---------------------------------------------------------------------------
# Text cleanup
# ---------------------------------------------------------------------------


def _normalize_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def _split_paragraphs(raw: str) -> list[str]:
    """Split page text on blank lines; drop empty / whitespace-only blocks."""
    if not raw:
        return []
    paragraphs: list[str] = []
    for chunk in raw.split("\n\n"):
        cleaned = _normalize_whitespace(chunk.replace("\n", " "))
        if cleaned:
            paragraphs.append(cleaned)
    # Fallback: if the page had no blank-line breaks, keep line-grouped text.
    if not paragraphs:
        cleaned = _normalize_whitespace(raw.replace("\n", " "))
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs
