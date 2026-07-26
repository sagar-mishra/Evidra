"""
FastAPI application entry point.

Run (from project root):
    uv run uvicorn app.main:app --app-dir backend --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import settings

app = FastAPI(
    title="Industrial Controls Release Assurance API",
    description=(
        "Read-only, human-reviewed release audit backend. "
        "Configurable hybrid AI (OpenAI default; Ollama/vLLM local fallback)."
    ),
    version="0.6.0",
)

# Local dev + Azure frontend origins from CORS_ORIGINS env
# Always allow both localhost and 127.0.0.1 for Next.js dev.
_cors = settings.cors_origins_list()
for _origin in (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
):
    if _origin not in _cors:
        _cors.append(_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Industrial Controls Release Assurance",
        "docs": "/docs",
        "health": "/api/v1/health",
        "mock_findings": "GET /api/v1/mock-findings",
        "analyze": "POST /api/v1/analyze",
        "generate_test": "POST /api/v1/generate-test",
    }
