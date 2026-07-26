"""
Application settings (Azure + local).

LLM providers (priority default: Anthropic): anthropic | openai | gemini | ollama | vllm | local
Embeddings: openai | gemini | local (via LiteLLM / FastEmbed)

Loaded from environment variables and `.env` via pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Prefer backend/.env, then monorepo root .env
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_CANDIDATES = (
    _BACKEND_DIR / ".env",
    _PROJECT_ROOT / ".env",
)
_ENV_FILES = tuple(str(p) for p in _ENV_CANDIDATES if p.is_file())

LLMProvider = Literal["anthropic", "openai", "gemini", "ollama", "vllm", "local"]
# Anthropic has no native embeddings — Voyage is their recommended partner (VOYAGE_API_KEY).
EmbeddingProvider = Literal["voyage", "openai", "gemini", "local"]

# Default dual-model Anthropic pair (LiteLLM model ids)
_DEFAULT_LLM_FAST = "anthropic/claude-3-5-haiku-20241022"
_DEFAULT_LLM_REASONING = "anthropic/claude-3-5-sonnet-20240620"
_DEFAULT_VOYAGE_EMBEDDING = "voyage-4-lite"


# Known dense embedding dimensions (for Qdrant collection sizing).
# Gemini Embedding 1/2 default to 3072; use EMBEDDING_DIMENSIONS to truncate (768/1536).
# Voyage 4 series default to 1024 (Matryoshka: 256/512/1024/2048).
_EMBEDDING_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # Retired Gemini models (kept for alias resolution only)
    "text-embedding-004": 768,
    "embedding-001": 768,
    # Current Gemini Embedding API models (default output size)
    "gemini-embedding-001": 3072,
    "gemini-embedding-2": 3072,
    "gemini-embedding-2-preview": 3072,
    # Voyage AI (Anthropic-recommended embeddings partner)
    "voyage-4-lite": 1024,
    "voyage-4": 1024,
    "voyage-4-large": 1024,
    "voyage-4-nano": 1024,
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "voyage-3.5": 1024,
    "voyage-3.5-lite": 1024,
    "voyage-3-large": 1024,
    "voyage-code-3": 1024,
    "BAAI/bge-small-en-v1.5": 384,
    "bge-small-en-v1.5": 384,
}

# Retired Gemini embedding ids → current LiteLLM-compatible model names
_GEMINI_EMBEDDING_ALIASES: dict[str, str] = {
    "text-embedding-004": "gemini-embedding-001",
    "embedding-001": "gemini-embedding-001",
    "models/text-embedding-004": "gemini-embedding-001",
    "models/embedding-001": "gemini-embedding-001",
    "textembedding-gecko": "gemini-embedding-001",
    "textembedding-gecko-001": "gemini-embedding-001",
}


class Settings(BaseSettings):
    """Runtime configuration for AI providers, Qdrant, and inference endpoints."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES if _ENV_FILES else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- API keys ---
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key (default LLM provider).",
    )
    VOYAGE_API_KEY: Optional[str] = Field(
        default=None,
        description=(
            "Voyage AI API key for dense embeddings (voyage-4-lite etc.). "
            "Anthropic does not embed natively; Voyage is their recommended partner. "
            "Get a key at https://dash.voyageai.com/ (NOT the Claude/Anthropic key)."
        ),
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key (LLM + embeddings when provider is openai).",
    )
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini / Generative Language API key.",
    )

    # --- HTTP / CORS ---
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description=(
            "Comma-separated browser origins allowed by CORS. "
            "Include the deployed Next.js URL in Azure."
        ),
    )

    # --- Qdrant ---
    QDRANT_URL: str = Field(
        default="http://localhost:6333",
        description="Qdrant HTTP URL (local Docker or Qdrant Cloud).",
    )
    QDRANT_API_KEY: str | None = Field(
        default=None,
        description="Qdrant Cloud API key. Leave empty for local Qdrant.",
    )
    QDRANT_IN_MEMORY: bool = Field(
        default=False,
        description="If true, use in-process :memory: Qdrant (ignore URL/key).",
    )
    QDRANT_TIMEOUT: float = Field(default=120.0, ge=5.0, le=600.0)
    QDRANT_UPSERT_BATCH_SIZE: int = Field(default=16, ge=1, le=256)
    QDRANT_UPSERT_RETRIES: int = Field(default=4, ge=1, le=10)

    # --- LLM: dual-model architecture (Anthropic priority) ---
    LLM_PROVIDER: LLMProvider = Field(
        default="anthropic",
        description="LLM provider: anthropic | openai | gemini | ollama | vllm | local",
    )
    # Fast / lightweight tasks (formatting, simple drafts)
    LLM_MODEL_NAME: str = Field(
        default=_DEFAULT_LLM_FAST,
        description=(
            "Fast model for lightweight tasks. "
            "Default: anthropic/claude-3-5-haiku-20241022. "
            "OpenAI: gpt-4o-mini. Gemini: gemini-2.0-flash."
        ),
    )
    # Complex controls-engineering reasoning only (StrictFindingSchema)
    LLM_REASONING_MODEL: str = Field(
        default=_DEFAULT_LLM_REASONING,
        description=(
            "Strong model for constrained finding evaluation. "
            "Default: anthropic/claude-3-5-sonnet-20240620. "
            "OpenAI: gpt-4o. Gemini: gemini-2.5-pro."
        ),
    )
    LLM_API_BASE: str | None = Field(
        default=None,
        description="Optional API base (Ollama/vLLM). Leave unset for cloud public APIs.",
    )
    LLM_TEMPERATURE: float = Field(default=0.1, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(default=2048, ge=64, le=128000)

    # --- Dense embeddings ---
    # Default voyage-4-lite when pairing with Anthropic LLMs (requires VOYAGE_API_KEY).
    EMBEDDING_PROVIDER: EmbeddingProvider = Field(
        default="voyage",
        description="Dense embedding provider: voyage | openai | gemini | local",
    )
    EMBEDDING_MODEL_NAME: str = Field(
        default=_DEFAULT_VOYAGE_EMBEDDING,
        description=(
            "Dense embedding model name. "
            "Voyage (Anthropic-recommended): voyage-4-lite (default). "
            "OpenAI: text-embedding-3-small. "
            "Gemini: gemini-embedding-001. "
            "Local: BAAI/bge-small-en-v1.5."
        ),
    )
    EMBEDDING_DIMENSIONS: int | None = Field(
        default=None,
        ge=128,
        le=3072,
        description=(
            "Optional output dimensionality override (Matryoshka truncation). "
            "Voyage 4: 256/512/1024/2048 (default 1024). "
            "Gemini: 768 or 1536. Leave unset for model default."
        ),
    )
    # Backward-compatible alias (if set in older .env files)
    OPENAI_EMBEDDING_MODEL: str | None = Field(
        default=None,
        description="Deprecated alias for EMBEDDING_MODEL_NAME when using OpenAI.",
    )
    LOCAL_EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="FastEmbed model when EMBEDDING_PROVIDER=local.",
    )
    SPARSE_EMBEDDING_MODEL: str = Field(
        default="Qdrant/bm25",
        description="Local sparse BM25 model for hybrid RRF.",
    )

    @field_validator("LLM_PROVIDER", "EMBEDDING_PROVIDER", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object, info: object) -> object:
        if not isinstance(value, str):
            return value
        v = value.strip().lower()
        field = getattr(info, "field_name", None)
        if v in {"google", "google-gemini"}:
            return "gemini"
        if v in {"claude", "anthropic-claude"}:
            return "anthropic"
        # Voyage aliases (embeddings only — do not remap LLM_PROVIDER=anthropic)
        if field == "EMBEDDING_PROVIDER" and v in {
            "voyageai",
            "voyage-ai",
            "voyage_ai",
        }:
            return "voyage"
        return v

    @field_validator("ANTHROPIC_API_KEY", "VOYAGE_API_KEY", "QDRANT_API_KEY", mode="before")
    @classmethod
    def _empty_api_key_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("QDRANT_URL", mode="before")
    @classmethod
    def _strip_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value

    @model_validator(mode="after")
    def _apply_aliases_and_llm_fallback(self) -> Settings:
        # Honor legacy OPENAI_EMBEDDING_MODEL if EMBEDDING_MODEL_NAME left at default
        # and user only set the old variable.
        if self.OPENAI_EMBEDDING_MODEL and self.OPENAI_EMBEDDING_MODEL.strip():
            if (
                self.EMBEDDING_PROVIDER == "openai"
                and self.EMBEDDING_MODEL_NAME == "text-embedding-3-small"
                and self.OPENAI_EMBEDDING_MODEL.strip() != "text-embedding-3-small"
            ):
                object.__setattr__(
                    self, "EMBEDDING_MODEL_NAME", self.OPENAI_EMBEDDING_MODEL.strip()
                )

        # Migrate retired Gemini embedding model names automatically
        bare = self.EMBEDDING_MODEL_NAME.strip()
        bare_key = bare.split("/")[-1]
        if bare_key in _GEMINI_EMBEDDING_ALIASES:
            migrated = _GEMINI_EMBEDDING_ALIASES[bare_key]
            object.__setattr__(self, "EMBEDDING_MODEL_NAME", migrated)
        elif bare in _GEMINI_EMBEDDING_ALIASES:
            object.__setattr__(
                self, "EMBEDDING_MODEL_NAME", _GEMINI_EMBEDDING_ALIASES[bare]
            )

        # Sensible Gemini default: truncate to 768-d (quality ~ full 3072, cheaper Qdrant)
        if (
            self.EMBEDDING_PROVIDER == "gemini"
            and self.EMBEDDING_DIMENSIONS is None
            and self.EMBEDDING_MODEL_NAME.strip().startswith("gemini-embedding")
        ):
            object.__setattr__(self, "EMBEDDING_DIMENSIONS", 768)

        # Embedding fallback: voyage preferred with Anthropic stack; else openai/local
        self._apply_embedding_provider_fallback()

        # LLM provider fallback: anthropic preferred, then openai, then gemini
        self._apply_llm_provider_fallback()
        return self

    def _anthropic_key(self) -> str:
        return (self.ANTHROPIC_API_KEY or "").strip()

    def _voyage_key(self) -> str:
        return (self.VOYAGE_API_KEY or "").strip()

    def _apply_embedding_provider_fallback(self) -> None:
        """
        If EMBEDDING_PROVIDER=voyage but VOYAGE_API_KEY is missing, fall back to
        OpenAI (if key present) or leave voyage (caller will error / pipeline may
        switch to local).
        """
        if (self.EMBEDDING_PROVIDER or "").lower() != "voyage":
            return
        if self._voyage_key():
            # Normalize model name to bare voyage-* id
            name = self.EMBEDDING_MODEL_NAME.strip()
            if name.startswith("voyage/"):
                object.__setattr__(self, "EMBEDDING_MODEL_NAME", name.split("/", 1)[1])
            return
        # No Voyage key — fall back to OpenAI embeddings when available
        if self.OPENAI_API_KEY.strip():
            object.__setattr__(self, "EMBEDDING_PROVIDER", "openai")
            if self.EMBEDDING_MODEL_NAME.strip().startswith("voyage"):
                object.__setattr__(self, "EMBEDDING_MODEL_NAME", "text-embedding-3-small")
                if self.EMBEDDING_DIMENSIONS is not None:
                    object.__setattr__(self, "EMBEDDING_DIMENSIONS", None)

    def _apply_llm_provider_fallback(self) -> None:
        """
        If LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is missing, fall back to
        OpenAI or Gemini when those keys are present (and retarget default models).
        """
        provider = (self.LLM_PROVIDER or "").lower()
        if provider != "anthropic":
            return
        if self._anthropic_key():
            return

        openai_key = self.OPENAI_API_KEY.strip()
        gemini_key = self.GEMINI_API_KEY.strip()
        if openai_key:
            object.__setattr__(self, "LLM_PROVIDER", "openai")
            # Only swap models if still on Anthropic defaults / prefixed anthropic/
            if self._is_anthropic_model_name(self.LLM_MODEL_NAME):
                object.__setattr__(self, "LLM_MODEL_NAME", "gpt-4o-mini")
            if self._is_anthropic_model_name(self.LLM_REASONING_MODEL):
                object.__setattr__(self, "LLM_REASONING_MODEL", "gpt-4o")
            return
        if gemini_key:
            object.__setattr__(self, "LLM_PROVIDER", "gemini")
            if self._is_anthropic_model_name(self.LLM_MODEL_NAME):
                object.__setattr__(self, "LLM_MODEL_NAME", "gemini-2.0-flash")
            if self._is_anthropic_model_name(self.LLM_REASONING_MODEL):
                object.__setattr__(self, "LLM_REASONING_MODEL", "gemini-2.5-pro")

    @staticmethod
    def _is_anthropic_model_name(name: str) -> bool:
        n = (name or "").strip().lower()
        return (
            not n
            or n.startswith("anthropic/")
            or n.startswith("claude")
            or n in {_DEFAULT_LLM_FAST, _DEFAULT_LLM_REASONING}
        )

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def dense_embedding_model(self) -> str:
        """Bare model name used for dense embeddings."""
        if self.EMBEDDING_PROVIDER == "local":
            return self.LOCAL_EMBEDDING_MODEL
        return self.EMBEDDING_MODEL_NAME.strip()

    @property
    def dense_vector_size(self) -> int:
        """Qdrant dense vector dimensionality for the active embedding model."""
        if self.EMBEDDING_PROVIDER == "local":
            return 384
        # Explicit truncation / output dimensionality takes precedence
        if self.EMBEDDING_DIMENSIONS is not None:
            return int(self.EMBEDDING_DIMENSIONS)
        name = self.dense_embedding_model
        # Strip provider prefixes for lookup
        bare = name.split("/")[-1]
        if bare in _EMBEDDING_DIMS:
            return _EMBEDDING_DIMS[bare]
        if self.EMBEDDING_PROVIDER == "voyage":
            return 1024
        if self.EMBEDDING_PROVIDER == "openai":
            return 1536
        if self.EMBEDDING_PROVIDER == "gemini":
            return 3072
        return 1536

    def resolve_embedding_litellm_model(self) -> str:
        """LiteLLM / provider model id for dense embeddings."""
        name = self.dense_embedding_model
        provider = self.EMBEDDING_PROVIDER
        if provider == "local":
            return name
        if name.startswith(("openai/", "gemini/", "azure/", "voyage/")):
            return name
        if provider == "voyage":
            # Bare model for voyageai SDK; LiteLLM uses voyage/<name>
            bare = name.split("/")[-1]
            return f"voyage/{bare}"
        if provider == "openai":
            return f"openai/{name}" if not name.startswith("text-embedding") else name
        if provider == "gemini":
            # LiteLLM: gemini/gemini-embedding-001
            return f"gemini/{name}"
        return name

    def resolve_embedding_api_key(self) -> str | None:
        if self.EMBEDDING_PROVIDER == "voyage":
            key = self._voyage_key()
            return key or None
        if self.EMBEDDING_PROVIDER == "openai":
            key = self.OPENAI_API_KEY.strip()
            return key or None
        if self.EMBEDDING_PROVIDER == "gemini":
            key = self.GEMINI_API_KEY.strip()
            return key or None
        return None

    def resolve_litellm_model(self, *, reasoning: bool = False) -> str:
        """
        LiteLLM chat model string.

        reasoning=False → LLM_MODEL_NAME (fast tasks)
        reasoning=True  → LLM_REASONING_MODEL (StrictFinding / complex evaluation)
        """
        name = (
            self.LLM_REASONING_MODEL.strip()
            if reasoning
            else self.LLM_MODEL_NAME.strip()
        )
        provider = self.LLM_PROVIDER

        if name.startswith(
            (
                "openai/",
                "azure/",
                "gemini/",
                "anthropic/",
                "claude-",
                "ollama/",
                "ollama_chat/",
            )
        ):
            # LiteLLM accepts anthropic/claude-... ; bare claude-... also works with provider
            if name.startswith("claude-") and provider == "anthropic":
                return f"anthropic/{name}"
            return name

        if provider == "anthropic":
            return f"anthropic/{name}"
        if provider == "openai":
            return f"openai/{name}"
        if provider == "gemini":
            return f"gemini/{name}"
        if provider in {"ollama", "local"}:
            return f"ollama/{name}"
        if provider == "vllm":
            return f"openai/{name}"
        return name

    def resolve_llm_api_key(self) -> str | None:
        if self.LLM_PROVIDER == "anthropic":
            key = self._anthropic_key()
            return key or None
        if self.LLM_PROVIDER == "openai":
            key = self.OPENAI_API_KEY.strip()
            return key or None
        if self.LLM_PROVIDER == "gemini":
            key = self.GEMINI_API_KEY.strip()
            return key or None
        return None

    def resolve_llm_api_base(self) -> str | None:
        if self.LLM_API_BASE:
            return self.LLM_API_BASE.rstrip("/")
        if self.LLM_PROVIDER in {"ollama", "local"}:
            return "http://localhost:11434"
        if self.LLM_PROVIDER == "vllm":
            return "http://localhost:8000/v1"
        return None

    @property
    def qdrant_api_key(self) -> str | None:
        key = self.QDRANT_API_KEY
        if key is None or not str(key).strip():
            return None
        return str(key).strip()

    @property
    def qdrant_uses_memory(self) -> bool:
        return bool(self.QDRANT_IN_MEMORY)

    @property
    def qdrant_is_cloud(self) -> bool:
        if self.qdrant_uses_memory:
            return False
        url = (self.QDRANT_URL or "").lower()
        local = any(
            host in url
            for host in ("localhost", "127.0.0.1", "0.0.0.0", "qdrant:6333")
        )
        return bool(self.qdrant_api_key) and not local

    def describe_qdrant_target(self) -> str:
        if self.qdrant_uses_memory:
            return "in-memory (:memory:)"
        key = "with API key" if self.qdrant_api_key else "no API key"
        kind = "cloud" if self.qdrant_is_cloud else "local/server"
        return f"{kind} {self.QDRANT_URL} ({key})"

    def require_provider_keys(self) -> None:
        """Fail loudly when a cloud provider is selected without its API key."""
        if self.LLM_PROVIDER == "anthropic" and not self._anthropic_key():
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic "
                "(or set OPENAI_API_KEY / GEMINI_API_KEY for automatic fallback)."
            )
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY.strip():
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY.strip():
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        if self.EMBEDDING_PROVIDER == "voyage" and not self._voyage_key():
            raise ValueError(
                "VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage. "
                "Get a key at https://dash.voyageai.com/ "
                "(Anthropic Claude keys do not work for Voyage embeddings)."
            )
        if self.EMBEDDING_PROVIDER == "openai" and not self.OPENAI_API_KEY.strip():
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        if self.EMBEDDING_PROVIDER == "gemini" and not self.GEMINI_API_KEY.strip():
            raise ValueError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini")

    def cors_origins_list(self) -> list[str]:
        """Parsed CORS allow-list (deduped, stripped)."""
        defaults = ["http://localhost:3000", "http://127.0.0.1:3000"]
        raw = [p.strip() for p in (self.CORS_ORIGINS or "").split(",") if p.strip()]
        merged: list[str] = []
        for origin in [*defaults, *raw]:
            if origin not in merged:
                merged.append(origin)
        return merged


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


# Module-level convenience: `from app.core.config import settings`
settings = get_settings()
