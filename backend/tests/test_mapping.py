"""
Milestone 3 validation script — Mapping & Rules Engine (Qdrant hybrid search).

Instantiates a local in-memory Qdrant hybrid engine, indexes dummy L5X tags,
runs hybrid search (dense + BM25 sparse + RRF) against a mock requirement, and
prints the ranked matches.

Usage (from project root):
    uv run python backend/tests/test_mapping.py

Note: first run downloads FastEmbed models (BAAI/bge-small-en-v1.5, Qdrant/bm25)
into the local FastEmbed cache. Subsequent runs are offline.
"""

from __future__ import annotations

import json
import sys

from app.ai.qdrant_engine import (
    QdrantEngineError,
    QdrantHybridEngine,
)
from app.core.config import settings
from app.schemas.mapping import TagIndexRecord

# ---------------------------------------------------------------------------
# Dummy PLC tags (not the full L5X — focused ranking fixture)
# ---------------------------------------------------------------------------

DUMMY_TAGS: list[TagIndexRecord] = [
    TagIndexRecord(
        tag_name="TMR_PUMP101_FailToStart",
        canonical_name="TMR_PUMP101_FAILTOSTART",
        description="Pump 101 fail-to-start delay timer preset in milliseconds",
        data_type="TIMER",
        equipment="PUMP101",
        role="FAILTOSTART",
    ),
    TagIndexRecord(
        tag_name="ALM_PUMP101_FailToStart",
        canonical_name="ALM_PUMP101_FAILTOSTART",
        description="Alarm: Pump 101 failed to start after proof timeout",
        data_type="BOOL",
        equipment="PUMP101",
        role="FAILTOSTART",
    ),
    TagIndexRecord(
        tag_name="CFG_PumpFlowProofTimeout_ms",
        canonical_name="CFG_PUMPFLOWPROOFTIMEOUT_MS",
        description="Chilled-water pump flow-proof timeout in milliseconds",
        data_type="DINT",
        equipment=None,
        role="TIMEOUT",
    ),
    TagIndexRecord(
        tag_name="AHU01_Permissive",
        canonical_name="AHU01_PERMISSIVE",
        description="AHU-01 start permissive including fire and leak interlocks",
        data_type="BOOL",
        equipment="AHU01",
        role="PERMISSIVE",
    ),
    TagIndexRecord(
        tag_name="CFG_CHW_DP_SP",
        canonical_name="CFG_CHW_DP_SP",
        description="CHW differential-pressure control setpoint",
        data_type="REAL",
        equipment=None,
        role="SP",
    ),
    TagIndexRecord(
        tag_name="CHWP02_FailoverRequest",
        canonical_name="CHWP02_FAILOVERREQUEST",
        description="Standby chilled-water pump failover request",
        data_type="BOOL",
        equipment="CHWP02",
        role="FAILOVERREQUEST",
    ),
    TagIndexRecord(
        tag_name="SYS_PostRunActive",
        canonical_name="SYS_POSTRUNACTIVE",
        description="System post-run sequence active flag",
        data_type="BOOL",
        equipment=None,
        role="POSTRUN",
    ),
]

# Mock SOO-style requirement (validation gate from plan.md)
MOCK_REQUIREMENT = "Pump 101 fail-to-start delay"

# Exact tag we expect hybrid RRF to rank first (strong BM25 + semantic overlap)
EXPECTED_TOP_TAG = "TMR_PUMP101_FailToStart"


def _divider(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> None:
    print("Milestone 3 — Mapping & Rules Engine (Qdrant Hybrid Search)")
    # Offline-friendly default for this smoke test: local dense + local BM25.
    # Production defaults (OpenAI dense) come from settings / .env.
    embedding_provider = "local"
    print(f"Dense provider : {embedding_provider} (test override; settings default={settings.EMBEDDING_PROVIDER})")
    print(f"Dense model    : {settings.LOCAL_EMBEDDING_MODEL} (384-d)")
    print(f"Sparse model   : {settings.SPARSE_EMBEDDING_MODEL} (local BM25)")
    print("Fusion         : Reciprocal Rank Fusion (RRF)")
    print("Storage        : in-memory local Qdrant")

    try:
        engine = QdrantHybridEngine(
            collection_name="m3_dummy_tags",
            recreate_collection=True,
            embedding_provider=embedding_provider,
            in_memory=True,
        )
    except QdrantEngineError as exc:
        print(f"ERROR: failed to start Qdrant engine: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _divider("INDEX DUMMY TAGS")
    try:
        count = engine.index_tags(DUMMY_TAGS)
    except QdrantEngineError as exc:
        print(f"ERROR: indexing failed: {exc}", file=sys.stderr)
        print(
            "Hint: first run needs network once to download FastEmbed models, "
            "or pre-seed the local FastEmbed cache for air-gapped hosts.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print(f"Indexed {count} tags (collection points={engine.count()})")
    for tag in DUMMY_TAGS:
        print(f"  - {tag.tag_name:32s} | {tag.description[:60]}")

    _divider(f"HYBRID SEARCH: {MOCK_REQUIREMENT!r}")
    try:
        result = engine.hybrid_search(MOCK_REQUIREMENT, limit=5)
    except QdrantEngineError as exc:
        print(f"ERROR: hybrid_search failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not result.hits:
        print("ERROR: no hits returned from hybrid search", file=sys.stderr)
        raise SystemExit(1)

    print(f"Top tag (RRF): {result.top_tag}")
    print("\nRanked hits:")
    for hit in result.hits:
        print(
            f"  #{hit.rank}  score={hit.score:.6f}  "
            f"tag={hit.tag_name:32s}  equipment={hit.equipment!s}"
        )
        print(f"       desc={hit.description}")

    _divider("VALIDATION")
    top = result.top_tag
    passed = top == EXPECTED_TOP_TAG
    payload = {
        "status": "OK" if passed else "FAIL",
        "query": MOCK_REQUIREMENT,
        "expected_top_tag": EXPECTED_TOP_TAG,
        "actual_top_tag": top,
        "top_score": result.hits[0].score,
        "ranked_tags": [h.tag_name for h in result.hits],
        "indexed_tag_count": count,
        "dense_model": engine.dense_model,
        "sparse_model": engine.sparse_model,
        "embedding_provider": engine.embedding_provider,
        "dense_vector_size": engine.dense_vector_size,
        "fusion": "RRF",
    }
    print(json.dumps(payload, indent=2))

    if not passed:
        print(
            f"\nFAILED: expected top tag {EXPECTED_TOP_TAG!r}, got {top!r}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("\nAll Milestone 3 hybrid-search checks PASSED.")
    print("Matched tag:", top)
    print("Milestone 3 mapping engine completed successfully.")


if __name__ == "__main__":
    main()
