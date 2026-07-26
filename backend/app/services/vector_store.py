"""
Qdrant client factory driven by environment variables.

| Env | Behavior |
|-----|----------|
| ``QDRANT_IN_MEMORY=true`` | Ephemeral in-process Qdrant (``:memory:``) |
| ``QDRANT_URL`` only | Local/server Qdrant, no auth |
| ``QDRANT_URL`` + ``QDRANT_API_KEY`` | Authenticated (Qdrant Cloud / secured) |

Cloud writes can be slow — ``QDRANT_TIMEOUT`` (default 120s) is applied to the HTTP client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from app.core.config import settings


def create_qdrant_client(
    *,
    url: str | None = None,
    api_key: str | None = None,
    path: str | Path | None = None,
    in_memory: bool | None = None,
    timeout: float | None = None,
    **kwargs: Any,
) -> QdrantClient:
    """
    Build a QdrantClient from settings (or explicit overrides).

    Priority:
      1. ``in_memory=True`` (arg or ``settings.QDRANT_IN_MEMORY``) → ``:memory:``
      2. ``path`` set → local on-disk embedded storage
      3. else → HTTP client at ``QDRANT_URL`` with optional ``QDRANT_API_KEY``
    """
    use_memory = settings.QDRANT_IN_MEMORY if in_memory is None else in_memory
    if use_memory:
        return QdrantClient(location=":memory:", **kwargs)

    if path is not None:
        disk_path = Path(path)
        disk_path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(disk_path), **kwargs)

    resolved_url = (url or settings.QDRANT_URL).rstrip("/")
    if api_key is not None:
        resolved_key = api_key.strip() if str(api_key).strip() else None
    else:
        resolved_key = settings.qdrant_api_key

    # Cloud clusters need a longer timeout than the client default (~5–10s).
    resolved_timeout = (
        float(timeout) if timeout is not None else float(settings.QDRANT_TIMEOUT)
    )

    client_kwargs: dict[str, Any] = {
        "url": resolved_url,
        "timeout": resolved_timeout,
        **kwargs,
    }
    # Only pass api_key when present — empty means local unauthenticated Qdrant
    if resolved_key:
        client_kwargs["api_key"] = resolved_key

    # Prefer REST for cloud compatibility; prefer_grpc can hang on some plans
    client_kwargs.setdefault("prefer_grpc", False)

    return QdrantClient(**client_kwargs)
