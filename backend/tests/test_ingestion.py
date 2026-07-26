"""
Milestone 1 validation script (enterprise monorepo layout).

Runs app.services parsers against ../../sample_data/ and prints a sample of
extracted tags and SOO text blocks to the terminal.

Usage (from project root):
    uv run python backend/tests/test_ingestion.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.services.doc_parser import DocumentParseError, parse_document
from app.services.lxml_parser import CHANGE_CLASSES, L5XParseError, parse_l5x

# backend/tests/ -> ../../sample_data/
SAMPLE_DIR = (Path(__file__).resolve().parent / ".." / ".." / "sample_data").resolve()

BASELINE_L5X = SAMPLE_DIR / "DC1_Cooling_Baseline_RevA.L5X"
REVISED_L5X = SAMPLE_DIR / "DC1_Cooling_Revised_RevB.L5X"
SOO_PDF = SAMPLE_DIR / "DC1_Cooling_SOO_RevB.pdf"
SOO_DOCX = SAMPLE_DIR / "DC1_Cooling_SOO_RevB.docx"

# How many items to print as a terminal sample
TAG_SAMPLE_SIZE = 8
RUNG_SAMPLE_SIZE = 3
TEXT_BLOCK_SAMPLE_SIZE = 5


def _divider(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _print_l5x_sample(label: str, path: Path) -> dict:
    _divider(f"L5X: {label}  ({path.as_posix()})")
    try:
        result = parse_l5x(path)
    except L5XParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    summary = result["summary"]
    controller = result["controller"]
    print(f"Controller : {controller.get('name')} ({controller.get('processor_type')})")
    print(f"Tags       : {summary['tag_count']}")
    print(f"Programs   : {summary['program_count']}")
    print(f"Routines   : {summary['routine_count']}")
    print(f"Rungs      : {summary['rung_count']}")
    print(f"Stripped metadata attrs: {result['stripped_metadata_attrs']}")
    print(f"Change classes (frozen): {result['change_classes']}")

    print(f"\n--- Sample tags (first {TAG_SAMPLE_SIZE}) ---")
    for i, (name, tag) in enumerate(result["tags"].items()):
        if i >= TAG_SAMPLE_SIZE:
            break
        print(
            f"  [{i + 1}] {name:40s}  type={tag['data_type']:6s}  "
            f"value={tag['value']!s:10s}  desc={tag['description']!r}"
        )

    # Highlight a few CFG setpoints that differ baseline vs revised
    cfg_keys = [
        "CFG_CHW_DP_SP",
        "CFG_PumpFlowProofTimeout_ms",
        "CFG_SAT_High_SP",
        "CFG_CHW_SuctionLowTrip_SP",
    ]
    print("\n--- Key CFG tag values ---")
    for key in cfg_keys:
        tag = result["tags"].get(key)
        if tag:
            print(f"  {key:35s} = {tag['value']}")

    # Sample rungs from first program
    print(f"\n--- Sample logic rungs (up to {RUNG_SAMPLE_SIZE} per routine, first 2 routines) ---")
    for prog_name, prog in list(result["programs"].items())[:1]:
        print(f"  Program: {prog_name}  main={prog['main_routine']}")
        for rout_name, rout in list(prog["routines"].items())[:2]:
            print(f"    Routine: {rout_name}  type={rout['type']}  rungs={rout['rung_count']}")
            for rung in rout["rungs"][:RUNG_SAMPLE_SIZE]:
                text_preview = (rung["text"] or "")[:90]
                comment_preview = (rung["comment"] or "")[:60]
                print(f"      Rung {rung['number']}: {text_preview}")
                if comment_preview:
                    print(f"               // {comment_preview}")

    return result


def _print_doc_sample(label: str, path: Path) -> dict:
    _divider(f"SOO: {label}  ({path.as_posix()})")
    try:
        result = parse_document(path)
    except DocumentParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Format     : {result['format']}")
    print(f"Blocks     : {result['block_count']}")
    if "page_count" in result:
        print(f"Pages      : {result['page_count']}")
    if "paragraph_count" in result:
        print(f"Paragraphs : {result['paragraph_count']}")

    print(f"\n--- Sample text blocks (first {TEXT_BLOCK_SAMPLE_SIZE}) ---")
    for block in result["text_blocks"][:TEXT_BLOCK_SAMPLE_SIZE]:
        preview = block["text"][:160]
        if len(block["text"]) > 160:
            preview += "..."
        loc = f"page={block['page']}" if block.get("page") is not None else f"index={block['index']}"
        print(f"  [{block['block_id']}] ({loc})")
        print(f"      {preview}")

    # Prefer blocks that look like requirements for a more useful sample
    req_blocks = [
        b for b in result["text_blocks"] if "REQ-" in b["text"] or "Requirement" in b["text"]
    ]
    if req_blocks:
        print(f"\n--- Sample requirement-like blocks ({min(3, len(req_blocks))} of {len(req_blocks)}) ---")
        for block in req_blocks[:3]:
            preview = block["text"][:200]
            if len(block["text"]) > 200:
                preview += "..."
            print(f"  [{block['block_id']}] {preview}")

    return result


def main() -> None:
    print("Milestone 1 — L5X & Document Ingestion (enterprise layout)")
    print(f"Sample directory: {SAMPLE_DIR.as_posix()}")
    print(f"Frozen change classes: {list(CHANGE_CLASSES)}")

    missing = [p for p in (BASELINE_L5X, REVISED_L5X, SOO_PDF, SOO_DOCX) if not p.is_file()]
    if missing:
        print("ERROR: Missing sample files:", file=sys.stderr)
        for p in missing:
            print(f"  - {p.as_posix()}", file=sys.stderr)
        raise SystemExit(1)

    baseline = _print_l5x_sample("Baseline RevA", BASELINE_L5X)
    revised = _print_l5x_sample("Revised RevB", REVISED_L5X)
    soo_pdf = _print_doc_sample("PDF", SOO_PDF)
    soo_docx = _print_doc_sample("DOCX", SOO_DOCX)

    _divider("INGESTION SUMMARY")
    print(
        json.dumps(
            {
                "baseline_tags": baseline["summary"]["tag_count"],
                "baseline_routines": baseline["summary"]["routine_count"],
                "baseline_rungs": baseline["summary"]["rung_count"],
                "revised_tags": revised["summary"]["tag_count"],
                "revised_routines": revised["summary"]["routine_count"],
                "revised_rungs": revised["summary"]["rung_count"],
                "soo_pdf_blocks": soo_pdf["block_count"],
                "soo_docx_blocks": soo_docx["block_count"],
                "change_classes": list(CHANGE_CLASSES),
                "module_imports": "app.services.lxml_parser / app.services.doc_parser",
                "status": "OK",
            },
            indent=2,
        )
    )
    print("\nMilestone 1 ingestion completed successfully.")


if __name__ == "__main__":
    main()
