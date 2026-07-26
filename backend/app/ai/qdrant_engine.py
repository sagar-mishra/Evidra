"""
Configurable hybrid search engine (Qdrant + dense embeddings + local BM25).

Dense (semantic) — routed by ``settings.EMBEDDING_PROVIDER`` / ``EMBEDDING_MODEL_NAME``:
  - Voyage ``voyage-4-lite`` via Voyage AI SDK (1024-d)  [default; Anthropic-recommended]
  - OpenAI ``text-embedding-3-small`` via ``litellm.embedding()`` (1536-d)
  - Gemini ``gemini-embedding-001`` via ``litellm.embedding()`` (768-d truncated)
  - Local ``BAAI/bge-small-en-v1.5`` via FastEmbed (384-d)                 [air-gapped]

  Anthropic has no native embeddings API; use Voyage (``VOYAGE_API_KEY``).

Sparse (lexical): always local ``Qdrant/bm25`` via FastEmbed.

Fusion: Reciprocal Rank Fusion (RRF) + optional deterministic lexical boost.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Sequence

from litellm import embedding as litellm_embedding
from qdrant_client import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.schemas.mapping import (
    HybridSearchHit,
    HybridSearchResult,
    TagIndexRecord,
)
from app.services.name_normalizer import normalize_identity
from app.services.vector_store import create_qdrant_client

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DEFAULT_COLLECTION = "plc_tags"

# Re-export names used by tests / callers
DENSE_MODEL = settings.dense_embedding_model
SPARSE_MODEL = settings.SPARSE_EMBEDDING_MODEL
DENSE_VECTOR_SIZE = settings.dense_vector_size


class QdrantEngineError(RuntimeError):
    """Raised when the vector engine cannot complete an operation."""


class QdrantHybridEngine:
    """
    Local Qdrant hybrid index for PLC tags.

    Dense provider and dimension are taken from ``settings``
    (``EMBEDDING_PROVIDER``: openai | gemini | local). Sparse BM25 is always local.
    """

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        recreate_collection: bool = False,
        embedding_provider: str | None = None,
        in_memory: bool | None = None,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        in_memory:
            ``None`` (default) → use ``settings.QDRANT_IN_MEMORY`` from ``.env``.
            ``True`` / ``False`` → force memory or HTTP regardless of env.
        qdrant_url / qdrant_api_key:
            Optional overrides; default to ``QDRANT_URL`` / ``QDRANT_API_KEY``.
        """
        self.collection_name = collection_name
        self.embedding_provider = (
            embedding_provider or settings.EMBEDDING_PROVIDER
        ).lower()
        if self.embedding_provider not in {"voyage", "openai", "gemini", "local"}:
            raise QdrantEngineError(
                f"Unsupported EMBEDDING_PROVIDER={self.embedding_provider!r}; "
                "use 'voyage', 'openai', 'gemini', or 'local'."
            )
        self._voyage_client: Any | None = None

        self.sparse_model_name = settings.SPARSE_EMBEDDING_MODEL
        self.dense_model = settings.dense_embedding_model
        self.dense_vector_size = settings.dense_vector_size
        self.dense_litellm_model = settings.resolve_embedding_litellm_model()

        # Back-compat attributes referenced by tests
        self.sparse_model = self.sparse_model_name

        self._path = Path(path) if path is not None else None
        self._sparse_embedder: Any | None = None
        self._local_dense_embedder: Any | None = None

        # Resolve target: env-driven unless caller overrides in_memory
        resolved_memory = (
            settings.QDRANT_IN_MEMORY if in_memory is None else in_memory
        )
        self.qdrant_target = (
            "in-memory"
            if resolved_memory
            else settings.describe_qdrant_target()
        )

        try:
            self.client = create_qdrant_client(
                path=self._path,
                in_memory=resolved_memory,
                url=qdrant_url,
                api_key=qdrant_api_key,
            )
        except Exception as exc:  # pragma: no cover
            raise QdrantEngineError(
                f"Failed to start Qdrant client ({self.qdrant_target}): {exc}"
            ) from exc

        self._ensure_collection(recreate=recreate_collection)

    # ------------------------------------------------------------------
    # Collection lifecycle
    # ------------------------------------------------------------------

    def _ensure_collection(self, *, recreate: bool = False) -> None:
        exists = self.client.collection_exists(self.collection_name)
        if exists and recreate:
            self.client.delete_collection(self.collection_name)
            exists = False

        if exists:
            # Fail loudly if an existing collection has the wrong dense size
            info = self.client.get_collection(self.collection_name)
            vectors = info.config.params.vectors
            current_size: int | None = None
            if isinstance(vectors, dict) and DENSE_VECTOR_NAME in vectors:
                current_size = int(vectors[DENSE_VECTOR_NAME].size)
            elif hasattr(vectors, "size"):
                current_size = int(vectors.size)  # type: ignore[union-attr]
            if current_size is not None and current_size != self.dense_vector_size:
                raise QdrantEngineError(
                    f"Collection '{self.collection_name}' has dense size {current_size}, "
                    f"but EMBEDDING_PROVIDER={self.embedding_provider!r} requires "
                    f"{self.dense_vector_size}. Recreate the collection "
                    f"(recreate_collection=True) or switch providers."
                )
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=self.dense_vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                )
            },
        )

    def reset(self) -> None:
        """Drop and recreate the collection (test helper)."""
        self._ensure_collection(recreate=True)

    def count(self) -> int:
        info = self.client.get_collection(self.collection_name)
        return int(info.points_count or 0)

    # ------------------------------------------------------------------
    # Embedding backends
    # ------------------------------------------------------------------

    def _get_sparse_embedder(self) -> Any:
        if self._sparse_embedder is None:
            try:
                from fastembed import SparseTextEmbedding
            except ImportError as exc:  # pragma: no cover
                raise QdrantEngineError(
                    "fastembed is required for local BM25 sparse embeddings"
                ) from exc
            self._sparse_embedder = SparseTextEmbedding(
                model_name=self.sparse_model_name
            )
        return self._sparse_embedder

    def _get_local_dense_embedder(self) -> Any:
        if self._local_dense_embedder is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:  # pragma: no cover
                raise QdrantEngineError(
                    "fastembed is required for local dense embeddings"
                ) from exc
            self._local_dense_embedder = TextEmbedding(model_name=self.dense_model)
        return self._local_dense_embedder

    def _embed_dense(
        self,
        texts: list[str],
        *,
        input_type: str | None = None,
    ) -> list[list[float]]:
        """
        Dense embed a batch of texts.

        For Voyage, pass ``input_type='document'`` when indexing and
        ``input_type='query'`` when searching (recommended by Voyage/Anthropic).
        """
        if not texts:
            return []
        if self.embedding_provider == "local":
            return self._embed_dense_local(texts)
        if self.embedding_provider == "voyage":
            return self._embed_dense_voyage(texts, input_type=input_type or "document")
        # openai | gemini via LiteLLM
        return self._embed_dense_litellm(texts)

    def _get_voyage_client(self) -> Any:
        if self._voyage_client is None:
            try:
                import voyageai
            except ImportError as exc:  # pragma: no cover
                raise QdrantEngineError(
                    "voyageai package is required for EMBEDDING_PROVIDER=voyage. "
                    "Install with: uv add voyageai"
                ) from exc
            api_key = settings.resolve_embedding_api_key()
            if not api_key:
                raise QdrantEngineError(
                    "VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage. "
                    "Get a key at https://dash.voyageai.com/ "
                    "(this is NOT your Anthropic Claude API key)."
                )
            self._voyage_client = voyageai.Client(api_key=api_key)
        return self._voyage_client

    def _embed_dense_voyage(
        self,
        texts: list[str],
        *,
        input_type: str = "document",
    ) -> list[list[float]]:
        """
        Voyage AI embeddings (Anthropic-recommended partner).

        Uses the official ``voyageai`` SDK for voyage-4-lite / voyage-4 / etc.
        """
        client = self._get_voyage_client()
        model = self.dense_model.split("/")[-1]
        # Voyage free/paid rate limits — moderate batch size
        chunk_size = 32
        max_retries = 5
        base_sleep = 2.0
        output_dim = (
            int(settings.EMBEDDING_DIMENSIONS)
            if settings.EMBEDDING_DIMENSIONS is not None
            else None
        )

        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), chunk_size):
            chunk = texts[start : start + chunk_size]
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    kwargs: dict[str, Any] = {
                        "texts": chunk,
                        "model": model,
                        "input_type": input_type,
                    }
                    if output_dim is not None:
                        kwargs["output_dimension"] = output_dim
                    result = client.embed(**kwargs)
                    embeddings = list(result.embeddings)
                    if len(embeddings) != len(chunk):
                        raise QdrantEngineError(
                            f"Voyage returned {len(embeddings)} vectors for "
                            f"{len(chunk)} texts"
                        )
                    for vec in embeddings:
                        v = list(map(float, vec))
                        if len(v) != self.dense_vector_size:
                            raise QdrantEngineError(
                                f"Expected dense dim {self.dense_vector_size}, "
                                f"got {len(v)} from voyage/{model}. "
                                "Set EMBEDDING_DIMENSIONS or recreate collection."
                            )
                        all_vectors.append(v)
                    last_exc = None
                    break
                except QdrantEngineError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    msg = str(exc).lower()
                    is_rate = any(
                        t in msg
                        for t in ("429", "rate", "quota", "resource_exhausted", "retry")
                    )
                    if is_rate and attempt < max_retries:
                        delay = min(base_sleep * (2**attempt), 60.0)
                        time.sleep(delay)
                        continue
                    raise QdrantEngineError(
                        f"Dense embedding failed "
                        f"(provider=voyage, model={model}): {exc}"
                    ) from exc
            if last_exc is not None and len(all_vectors) < start + len(chunk):
                raise QdrantEngineError(
                    f"Dense embedding failed after retries "
                    f"(provider=voyage, model={model}): {last_exc}"
                )
            if start + chunk_size < len(texts):
                time.sleep(0.15)
        return all_vectors

    def _embed_dense_litellm(self, texts: list[str]) -> list[list[float]]:
        """
        Route dense embeddings through LiteLLM (OpenAI or Gemini).

        Gemini free tier is tight (~100 embed RPM). We:
          - chunk large inputs into provider-friendly batches
          - retry 429 / RESOURCE_EXHAUSTED with exponential backoff
        """
        api_key = settings.resolve_embedding_api_key()
        if not api_key:
            raise QdrantEngineError(
                f"API key required when EMBEDDING_PROVIDER={self.embedding_provider!r}. "
                "Set OPENAI_API_KEY, GEMINI_API_KEY, or VOYAGE_API_KEY in .env."
            )
        model = self.dense_litellm_model

        # Gemini free tier: fewer, larger batches reduce request count.
        # OpenAI: larger batches are fine.
        if self.embedding_provider == "gemini":
            chunk_size = 16
            max_retries = 6
            base_sleep = 5.0
        else:
            chunk_size = 64
            max_retries = 4
            base_sleep = 2.0

        all_vectors: list[list[float] | None] = [None] * len(texts)
        for start in range(0, len(texts), chunk_size):
            chunk = texts[start : start + chunk_size]
            vectors = self._embed_dense_litellm_chunk(
                chunk,
                model=model,
                api_key=api_key,
                max_retries=max_retries,
                base_sleep=base_sleep,
            )
            for offset, vec in enumerate(vectors):
                all_vectors[start + offset] = vec
            # Gentle pacing for Gemini free tier between chunks
            if self.embedding_provider == "gemini" and start + chunk_size < len(texts):
                time.sleep(1.0)

        if any(v is None for v in all_vectors):
            raise QdrantEngineError("Dense embedding returned incomplete batch")
        return [v for v in all_vectors if v is not None]

    def _embed_dense_litellm_chunk(
        self,
        texts: list[str],
        *,
        model: str,
        api_key: str,
        max_retries: int,
        base_sleep: float,
    ) -> list[list[float]]:
        """Single LiteLLM embedding request with rate-limit retries."""
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "input": texts,
                    "api_key": api_key,
                }
                if settings.EMBEDDING_DIMENSIONS is not None:
                    kwargs["dimensions"] = int(settings.EMBEDDING_DIMENSIONS)
                if self.embedding_provider == "gemini":
                    import os

                    os.environ.setdefault("GEMINI_API_KEY", api_key)
                    os.environ.setdefault("GOOGLE_API_KEY", api_key)
                response = litellm_embedding(**kwargs)
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                is_rate = any(
                    token in msg
                    for token in (
                        "429",
                        "rate limit",
                        "rate_limit",
                        "resource_exhausted",
                        "quota",
                        "retry in",
                    )
                )
                if is_rate and attempt < max_retries:
                    # Honor "retry in N" if present, else exponential backoff
                    delay = base_sleep * (2**attempt)
                    import re

                    m = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)\s*s", str(exc), re.I)
                    if m:
                        delay = max(delay, float(m.group(1)) + 1.0)
                    delay = min(delay, 90.0)
                    time.sleep(delay)
                    continue
                raise QdrantEngineError(
                    f"Dense embedding failed "
                    f"(provider={self.embedding_provider}, model={model}): {exc}"
                ) from exc

            data = getattr(response, "data", None) or (
                response.get("data") if isinstance(response, dict) else None
            )
            if not data:
                raise QdrantEngineError(
                    f"Embedding response contained no data (model={model})"
                )

            def _item_index(item: Any) -> int:
                if isinstance(item, dict):
                    return int(item.get("index", 0))
                return int(getattr(item, "index", 0))

            def _item_embedding(item: Any) -> list[float]:
                if isinstance(item, dict):
                    return list(item["embedding"])
                return list(getattr(item, "embedding"))

            ordered = sorted(data, key=_item_index)
            vectors = [_item_embedding(item) for item in ordered]
            if vectors and len(vectors[0]) != self.dense_vector_size:
                raise QdrantEngineError(
                    f"Expected dense dim {self.dense_vector_size}, "
                    f"got {len(vectors[0])} from {model}. "
                    "Update EMBEDDING_MODEL_NAME or collection config."
                )
            return vectors

        raise QdrantEngineError(
            f"Dense embedding failed after retries "
            f"(provider={self.embedding_provider}, model={model}): {last_exc}"
        )

    def _embed_dense_local(self, texts: list[str]) -> list[list[float]]:
        embedder = self._get_local_dense_embedder()
        try:
            vectors = [list(map(float, vec)) for vec in embedder.embed(texts)]
        except Exception as exc:
            raise QdrantEngineError(
                f"Local dense embedding failed ({self.dense_model}): {exc}"
            ) from exc
        if vectors and len(vectors[0]) != self.dense_vector_size:
            raise QdrantEngineError(
                f"Expected dense dim {self.dense_vector_size}, "
                f"got {len(vectors[0])} from {self.dense_model}"
            )
        return vectors

    def _embed_sparse(self, texts: list[str]) -> list[models.SparseVector]:
        embedder = self._get_sparse_embedder()
        try:
            embeddings = list(embedder.embed(texts))
        except Exception as exc:
            raise QdrantEngineError(
                f"Local BM25 sparse embedding failed ({self.sparse_model_name}): {exc}"
            ) from exc

        sparse_vectors: list[models.SparseVector] = []
        for emb in embeddings:
            indices = getattr(emb, "indices", None)
            values = getattr(emb, "values", None)
            if indices is None or values is None:
                raise QdrantEngineError("Sparse embedding missing indices/values")
            # numpy arrays or lists
            idx_list = indices.tolist() if hasattr(indices, "tolist") else list(indices)
            val_list = values.tolist() if hasattr(values, "tolist") else list(values)
            sparse_vectors.append(
                models.SparseVector(
                    indices=[int(i) for i in idx_list],
                    values=[float(v) for v in val_list],
                )
            )
        return sparse_vectors

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_tags(
        self,
        tags: Sequence[TagIndexRecord | dict[str, Any]],
        *,
        batch_size: int | None = None,
    ) -> int:
        """
        Index PLC tags for hybrid search.

        Dense vectors: OpenAI or local BAAI (per settings).
        Sparse vectors: always local BM25.

        Uses smaller batches + retries for Qdrant Cloud write timeouts.

        Returns the number of points upserted.
        """
        records = [self._coerce_record(t) for t in tags]
        if not records:
            return 0

        # Cloud-friendly default batch (env: QDRANT_UPSERT_BATCH_SIZE)
        size = batch_size if batch_size is not None else int(settings.QDRANT_UPSERT_BATCH_SIZE)

        for start in range(0, len(records), size):
            batch = records[start : start + size]
            texts = [r.embed_text() for r in batch]
            dense_vectors = self._embed_dense(texts, input_type="document")
            sparse_vectors = self._embed_sparse(texts)
            points: list[models.PointStruct] = []
            for record, dense, sparse in zip(
                batch, dense_vectors, sparse_vectors, strict=True
            ):
                payload = record.model_dump()
                payload["embed_text"] = record.embed_text()
                payload["dense_model"] = self.dense_model
                payload["embedding_provider"] = self.embedding_provider
                points.append(
                    models.PointStruct(
                        id=self._stable_point_id(
                            record.canonical_name or record.tag_name
                        ),
                        vector={
                            DENSE_VECTOR_NAME: dense,
                            SPARSE_VECTOR_NAME: sparse,
                        },
                        payload=payload,
                    )
                )
            self._upsert(points)
        return len(records)

    def index_parsed_l5x_tags(
        self,
        parsed_tags: dict[str, dict[str, Any]],
        *,
        batch_size: int | None = None,
    ) -> int:
        """Convenience: index tags from parse_l5x()['tags'] dictionaries."""
        records: list[TagIndexRecord] = []
        for name, tag in parsed_tags.items():
            identity = normalize_identity(name)
            records.append(
                TagIndexRecord(
                    tag_name=tag.get("name") or name,
                    canonical_name=identity.canonical_name,
                    description=tag.get("description") or "",
                    data_type=tag.get("data_type"),
                    equipment=identity.equipment or tag.get("equipment"),
                    role=identity.role,
                    value=str(tag["value"]) if tag.get("value") is not None else None,
                    scope=tag.get("scope") or "controller",
                    program=tag.get("program"),
                )
            )
        return self.index_tags(records, batch_size=batch_size)

    def _upsert(self, points: list[models.PointStruct]) -> None:
        """Upsert with retries on transient cloud write timeouts."""
        if not points:
            return
        retries = int(settings.QDRANT_UPSERT_RETRIES)
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True,
                )
                return
            except UnexpectedResponse as exc:
                last_exc = exc
                if not self._is_transient_qdrant_error(exc) or attempt >= retries:
                    raise QdrantEngineError(f"Qdrant upsert failed: {exc}") from exc
            except Exception as exc:
                last_exc = exc
                if not self._is_transient_qdrant_error(exc) or attempt >= retries:
                    raise QdrantEngineError(
                        f"Failed to index tags (batch={len(points)}, "
                        f"attempt={attempt}/{retries}, target={self.qdrant_target}): {exc}"
                    ) from exc
            # Exponential backoff: 2s, 4s, 8s, …
            time.sleep(min(2**attempt, 20))
        raise QdrantEngineError(
            f"Failed to index tags after {retries} attempts: {last_exc}"
        )

    @staticmethod
    def _is_transient_qdrant_error(exc: BaseException) -> bool:
        msg = str(exc).lower()
        return any(
            token in msg
            for token in (
                "timeout",
                "timed out",
                "deadline",
                "temporarily",
                "unavailable",
                "connection reset",
                "connection aborted",
                "503",
                "502",
                "504",
            )
        )

    @staticmethod
    def _coerce_record(tag: TagIndexRecord | dict[str, Any]) -> TagIndexRecord:
        if isinstance(tag, TagIndexRecord):
            return tag
        if not isinstance(tag, dict):
            raise QdrantEngineError(f"Unsupported tag record type: {type(tag)!r}")
        if "tag_name" not in tag:
            raise QdrantEngineError("Tag record dict requires 'tag_name'")
        identity = normalize_identity(tag["tag_name"])
        return TagIndexRecord(
            tag_name=tag["tag_name"],
            canonical_name=tag.get("canonical_name") or identity.canonical_name,
            description=tag.get("description") or "",
            data_type=tag.get("data_type"),
            equipment=tag.get("equipment") or identity.equipment,
            role=tag.get("role") or identity.role,
            value=tag.get("value"),
            scope=tag.get("scope") or "controller",
            program=tag.get("program"),
            metadata=tag.get("metadata") or {},
        )

    @staticmethod
    def _stable_point_id(key: str) -> str:
        """Deterministic UUID for a tag key (re-index overwrites same point)."""
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return str(uuid.UUID(digest[:32]))

    # ------------------------------------------------------------------
    # Hybrid search (dense + sparse + RRF)
    # ------------------------------------------------------------------

    def hybrid_search(
        self,
        query: str,
        *,
        limit: int = 5,
        prefetch_limit: int = 20,
        lexical_boost: bool = True,
    ) -> HybridSearchResult:
        """
        Hybrid search over indexed tags using dense + sparse prefetches fused
        with Reciprocal Rank Fusion (RRF).
        """
        cleaned = (query or "").strip()
        if not cleaned:
            raise QdrantEngineError("hybrid_search query must not be empty")
        if limit < 1:
            raise QdrantEngineError("limit must be >= 1")

        fetch_limit = max(limit, prefetch_limit) if lexical_boost else limit

        try:
            dense_q = self._embed_dense([cleaned], input_type="query")[0]
            sparse_q = self._embed_sparse([cleaned])[0]
            response = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    models.Prefetch(
                        query=dense_q,
                        using=DENSE_VECTOR_NAME,
                        limit=prefetch_limit,
                    ),
                    models.Prefetch(
                        query=sparse_q,
                        using=SPARSE_VECTOR_NAME,
                        limit=prefetch_limit,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=fetch_limit,
                with_payload=True,
                with_vectors=False,
            )
        except QdrantEngineError:
            raise
        except Exception as exc:
            raise QdrantEngineError(f"Hybrid search failed: {exc}") from exc

        hits: list[HybridSearchHit] = []
        for rank, point in enumerate(response.points, start=1):
            payload = dict(point.payload or {})
            hits.append(
                HybridSearchHit(
                    tag_name=str(payload.get("tag_name") or ""),
                    canonical_name=payload.get("canonical_name"),
                    description=payload.get("description"),
                    equipment=payload.get("equipment"),
                    score=float(point.score or 0.0),
                    rank=rank,
                    payload=payload,
                )
            )

        if lexical_boost and hits:
            hits = self._apply_lexical_boost(cleaned, hits)[:limit]
            for index, hit in enumerate(hits, start=1):
                hit.rank = index

        return HybridSearchResult(
            query=cleaned,
            collection=self.collection_name,
            hits=hits[:limit],
            top_tag=hits[0].tag_name if hits else None,
        )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        import re

        return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t}

    @classmethod
    def _apply_lexical_boost(
        cls,
        query: str,
        hits: list[HybridSearchHit],
    ) -> list[HybridSearchHit]:
        """Deterministic post-RRF re-rank (exact/alias/equipment/role)."""
        q_tokens = cls._tokenize(query)
        digits = {t for t in q_tokens if t.isdigit()}
        alphas = {t for t in q_tokens if t.isalpha()}
        compact_equip = {f"{a}{d}" for a in alphas for d in digits}

        role_hints = {
            "delay": ("tmr", "timer", "timeout", "delay"),
            "timer": ("tmr", "timer", "timeout", "delay"),
            "timeout": ("tmr", "timer", "timeout", "delay", "cfg"),
            "alarm": ("alm", "alarm"),
            "permissive": ("permissive", "interlock"),
            "failover": ("failover",),
            "setpoint": ("_sp", "setpoint", "cfg"),
        }

        rescored: list[HybridSearchHit] = []
        for hit in hits:
            blob = " ".join(
                [
                    hit.tag_name or "",
                    hit.canonical_name or "",
                    hit.description or "",
                    hit.equipment or "",
                ]
            ).lower()
            blob_tokens = cls._tokenize(blob)
            tag_compact = (hit.tag_name or "").lower().replace("_", "").replace("-", "")

            boost = 0.0
            overlap = q_tokens & blob_tokens
            boost += 0.05 * len(overlap)

            for equip in compact_equip:
                if equip in tag_compact or equip in blob.replace(" ", ""):
                    boost += 0.25

            for q_key, hints in role_hints.items():
                if q_key in q_tokens:
                    if any(h in blob for h in hints):
                        boost += 0.20
                    if q_key in {"delay", "timer"} and blob.startswith("alm_"):
                        if "delay" not in blob and "timer" not in blob:
                            boost -= 0.15

            if "fail-to-start" in query.lower() or "fail to start" in query.lower():
                if (
                    "fail-to-start" in blob
                    or "fail to start" in blob
                    or "failtostart" in tag_compact
                ):
                    boost += 0.15

            new_score = float(hit.score) + boost
            rescored.append(
                HybridSearchHit(
                    tag_name=hit.tag_name,
                    canonical_name=hit.canonical_name,
                    description=hit.description,
                    equipment=hit.equipment,
                    score=new_score,
                    rank=hit.rank,
                    payload={
                        **(hit.payload or {}),
                        "rrf_score": hit.score,
                        "lexical_boost": boost,
                    },
                )
            )

        rescored.sort(
            key=lambda h: (
                -h.score,
                0 if (h.tag_name or "").upper().startswith("TMR_") else 1,
                h.tag_name or "",
            )
        )
        return rescored

    def search_requirement(
        self,
        requirement_text: str,
        *,
        limit: int = 5,
    ) -> HybridSearchResult:
        """Alias used by mapping workflows for requirement → tag retrieval."""
        return self.hybrid_search(requirement_text, limit=limit)


def build_tag_records_from_dicts(
    tags: Iterable[dict[str, Any]],
) -> list[TagIndexRecord]:
    """Helper for tests and callers supplying lightweight dict tags."""
    return [QdrantHybridEngine._coerce_record(t) for t in tags]  # noqa: SLF001
