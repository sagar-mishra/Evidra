# Industrial Controls Release Assurance

Read-only, human-reviewed release audit tool for Rockwell PLC (L5X) projects.  
Compares baseline vs revised controller exports, maps changes to SOO/FDS requirements, drafts focused regression tests, and supports engineer Accept / Reject / Edit / Unresolved review before PDF/CSV export.

**Stack:** Python FastAPI backend · Next.js 14 frontend · Qdrant hybrid search · LiteLLM + Instructor (OpenAI by default, Ollama/vLLM optional)

---

## Prerequisites

- **Python 3.12+** and [uv](https://github.com/astral-sh/uv)
- **Node.js 18+** and npm (frontend)
- **OpenAI API key** (default hybrid config), *or* local Ollama for offline LLM/embeddings

---

## 1. Setup

### Backend

```powershell
# From project root
cd D:\AI-Projects\AI-Automation

# Install Python dependencies
uv sync

# Configure environment (backend/.env.example or monorepo root)
copy .env.example .env
# Edit .env — set OPENAI_API_KEY, optional QDRANT_URL / QDRANT_API_KEY
```

### Frontend

```powershell
cd D:\AI-Projects\AI-Automation\frontend
copy .env.example .env.local
npm install
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` (see `frontend/.env.example`).

---

## 2. Run the application

Use **two terminals** (backend + frontend).

### Terminal A — FastAPI backend

```powershell
cd D:\AI-Projects\AI-Automation
uv run uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Health: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- OpenAPI docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Terminal B — Next.js frontend

```powershell
cd D:\AI-Projects\AI-Automation\frontend
npm run dev
```

- UI: [http://localhost:3000](http://localhost:3000)

Open the UI in your browser:

1. **Upload** baseline L5X, revised L5X, and SOO PDF/DOCX → **Run Analysis**
2. Wait for the pipeline (diff → mapping → AI tests)
3. Review findings in the 3-pane workspace (queue · diff/SOO · test plan)
4. Accept / Reject / Edit · **Export PDF + CSV**

Optional: use **Load demo findings** on the upload screen to skip upload and use mock data.

---

## 3. Optional: local LLM (Ollama) instead of OpenAI

```powershell
# Pull and run a local model
ollama pull llama3.1
ollama serve
```

In `.env`:

```env
LLM_PROVIDER=ollama
LLM_MODEL_NAME=llama3.1
LLM_API_BASE=http://localhost:11434
EMBEDDING_PROVIDER=local
# OPENAI_API_KEY can be left empty when fully local
```

Then start backend + frontend as in section 2.

---

## 4. Validation / benchmark scripts

Run from the **project root** after `uv sync`.

```powershell
# Milestone 1 — L5X + SOO ingestion
uv run python backend/tests/test_ingestion.py

# Milestone 2 — Deterministic L5X diff
uv run python backend/tests/test_diff.py

# Milestone 3 — Qdrant hybrid mapping (local dense for smoke test)
uv run python backend/tests/test_mapping.py

# Milestone 4 — LLM regression test generation (needs OpenAI or Ollama)
uv run python backend/tests/test_generation.py

# Milestone 6 — End-to-end benchmark vs ground_truth.json
uv run python backend/tests/test_benchmark.py
```

Benchmark options:

```powershell
# Faster: skip LLM generation stage
$env:BENCHMARK_SKIP_LLM = "1"
uv run python backend/tests/test_benchmark.py

# Cap number of LLM generations
$env:BENCHMARK_LLM_LIMIT = "4"
uv run python backend/tests/test_benchmark.py
```

Report output: `sample_data/VALIDATION_REPORT.md`

---

## 5. Docker (Azure Container Apps prep)

Build from the **monorepo root** (backend) and **frontend/** context:

```powershell
# Backend API image
docker build -f backend/Dockerfile -t release-assurance-api .

# Frontend image (bake production API URL at build time)
docker build -f frontend/Dockerfile `
  --build-arg NEXT_PUBLIC_API_URL=https://your-api.azurecontainerapps.io `
  -t release-assurance-web ./frontend
```

Run locally:

```powershell
docker run --rm -p 8000:8000 --env-file .env release-assurance-api
docker run --rm -p 3000:3000 release-assurance-web
```

Qdrant: set `QDRANT_URL` + `QDRANT_API_KEY` for Qdrant Cloud; leave the key empty for local unauthenticated Qdrant at `http://localhost:6333`.

## 6. Project layout

```
sample_data/           # DC1 benchmark L5X, SOO, ground_truth.json
backend/
  app/
    main.py            # FastAPI entry
    api/               # Routes
    core/              # config.py (pydantic-settings)
    schemas/           # Pydantic models
    services/          # Deterministic parse/diff
    ai/                # Qdrant, LiteLLM, embeddings
  tests/               # Milestone validation scripts
frontend/
  src/app/             # Next.js 14 App Router UI
  src/lib/             # zustand store, export utilities
```

---

## 7. Environment variables (summary)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | OpenAI LLM/embeddings |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP endpoint |
| `QDRANT_API_KEY` | empty | Set for Qdrant Cloud; omit for local |
| `LLM_PROVIDER` | `openai` | `openai` \| `ollama` \| `vllm` \| `local` |
| `LLM_MODEL_NAME` | `gpt-4o-mini` | Chat model name |
| `EMBEDDING_PROVIDER` | `openai` | `openai` (1536-d) \| `local` (384-d BAAI) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → backend base URL |

See `backend/.env.example`, `frontend/.env.example`, and root `.env.example`.

---

## Safety note

This product is a **read-only, human-reviewed** audit aid. It never connects to live controllers, never auto-approves a release, and must not be used as operational control code. A qualified engineer must explicitly accept or reject all findings.
