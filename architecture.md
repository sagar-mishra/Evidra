# System Architecture & Tech Stack

## 1. Deployment Constraints
*   **100% Air-Gapped / FOSS:** The system must run entirely on local infrastructure with zero cloud data transmission to comply with industrial security requirements[cite: 1, 2].
*   **Containerization:** Full stack must be deployed via a single `docker-compose.yml`.

## 2. Technology Stack
*   **Frontend:** Next.js 14, Tailwind CSS, Shadcn UI.
*   **Backend:** Python FastAPI.
*   **Database:** PostgreSQL (with `pgvector` for audit logging and state).
*   **Vector Store:** Qdrant (Local/Embedded) for Hybrid Search.
*   **AI Inference:** vLLM or Ollama running local open-weights (e.g., Qwen 2.5 14B or Llama 3.1).

## 3. Core Processing Pipelines
The architecture uses a Hybrid Deterministic-Semantic Pipeline to prevent hallucinations:

### A. Deterministic XML Engine (L5X)
*   Use Python's `lxml` to parse Rockwell Studio 5000 XML exports[cite: 1].
*   **Sanitization:** Strip non-logical metadata (ToolID, ExportDate) before hashing to prevent false-positive diffs.
*   **Diff Engine:** Compare baseline and revised Abstract Syntax Trees (ASTs) deterministically to find changed tags, presets, and ladder logic instructions[cite: 1].

### B. Hybrid Semantic Mapping Engine
*   Map extracted unstructured requirements (from PDF) to precise PLC tags[cite: 1].
*   Use Qdrant Hybrid Search combining Sparse Vectors (`BM25` for exact tag matches) and Dense Vectors (`BAAI/bge-small-en-v1.5` for semantic intent).
*   Use Reciprocal Rank Fusion (RRF) to score the best matches.

### C. Configurable AI Generation Layer
*   **Router:** Use `LiteLLM` to wrap the local inference engine (allows instant switching between vLLM/Ollama).
*   **Schema Enforcement:** Use `Instructor` to force the LLM to output strictly validated Pydantic JSON schemas for Regression Test generation.

### D. Export Engine
*   Use `WeasyPrint` (or similar HTML-to-PDF library) to generate the final Release Assurance PDF document[cite: 1].