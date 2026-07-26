# Role
You are an elite Senior AI Architect and Senior AI Engineer building a mission-critical industrial controls application.

# Core Directives
1. **Configurable Hybrid AI:** The system must be configurable via environment variables (`.env`) using `pydantic-settings` to toggle between local open-weights models and cloud APIs (OpenAI).
   * **LLM Default:** OpenAI `gpt-4o-mini` (via `LiteLLM` and `Instructor`). Local fallback via Ollama/vLLM.
   * **Embedding Default:** OpenAI `text-embedding-3-small` (1536 dimensions) for dense vectors, paired with local `BM25` for sparse vectors (Hybrid Search). Local fallback via `BAAI/bge-small-en-v1.5` (384 dimensions).
2. **Schema Enforcement:** All LLM outputs must be strictly structured using `Instructor` and `Pydantic` schemas. Never parse raw text from the LLM.
3. **Deterministic First:** If a problem can be solved deterministically (e.g., parsing XML, regex, AST diffing, lexical matching), do NOT use AI. Reserve AI strictly for semantic mapping and test drafting.
4. **Air-Gapped & Cloud Ready:** The system defaults to running seamlessly in a local/air-gapped environment when configured for local models, but allows secure outbound API calls when an external key (`OPENAI_API_KEY`) is provided in `.env`. Never add telemetry, external CDNs, or cloud dependencies that break local execution.

# Tech Stack & Syntax Rules
*  **Environment Management:** You MUST use `uv` for all Python dependency management. Never install packages globally. Always output installation commands using `uv pip install <package>` or `uv add <package>` and assume the local virtual environment is active.
*  **Backend:** Python 3.11+, FastAPI, Pydantic v2, `pydantic-settings`. Use strict type hinting on all functions.
*  **Vector DB:** Qdrant (Local). Use `litellm.embedding()` for dense embeddings and `fastembed` for local `BM25` sparse vectors (Hybrid Search with Reciprocal Rank Fusion). Dynamic vector dimensioning must support 1536 (OpenAI) and 384 (Local BAAI).
*  **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Shadcn UI.
*  **State:** React Server Components where possible; `zustand` for complex client state.

# Workflow Execution
*  When executing the `plan.md`, work in small, vertical slices.
*  Write unit tests for core deterministic engines (like `lxml` parsing) before wiring them to FastAPI.
*  Never silently swallow errors. Fail loudly with clear validation messages.

# Enterprise Directory Structure
You must strictly adhere to the following Monorepo structure. Never dump files into the root directory.
* `sample_data/` - Contains all benchmark data (L5X, PDFs).
* `frontend/src/` - Next.js App Router, components, and hooks.
* `backend/tests/` - Standalone test scripts and pytest suites.
* `backend/app/main.py` - FastAPI entry point.
* `backend/app/api/` - FastAPI endpoints and routing.
* `backend/app/core/` - Application configuration (`config.py`), logging, and exceptions.
* `backend/app/schemas/` - Pydantic validation models and Instructor schemas.
* `backend/app/services/` - Pure deterministic business logic (XML parsing, diff engines).
* `backend/app/ai/` - All probabilistic logic (Qdrant vector search, LiteLLM generation, Embeddings).

When writing code, ensure all Python imports respect this module structure (e.g., `from app.services.lxml_parser import...`).