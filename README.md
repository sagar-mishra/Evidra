# Evidra

**Every change, proven before production.**

Industrial Controls Release Assurance for Rockwell PLC (L5X) projects.  
Compares baseline vs revised controller exports, maps changes to governing requirements, and produces evidence-backed regression tests for engineer review.

**Stack:** Python FastAPI backend · Next.js 14 frontend · Qdrant hybrid search · LiteLLM + Instructor (Anthropic / OpenAI / Gemini)

---

## Prerequisites

- **Python 3.12+** and [uv](https://github.com/astral-sh/uv)
- **Node.js 18+** and npm (frontend)
- **Docker Desktop** (for Azure deploy — Linux containers)
- **Azure CLI** (`az`) logged in (for deploy)
- API keys in root `.env` (see `.env.example`)

---

## 1. Setup

### Backend / monorepo env

```powershell
# From project root
cd D:\AI-Projects\AI-Automation

# Install Python dependencies
uv sync

# Configure environment
copy .env.example .env
# Edit .env — set API keys, Qdrant, ADMIN_USERNAME / ADMIN_PASSWORD
```

Important root `.env` keys:

```env
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
LLM_PROVIDER=anthropic
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-strong-password
```

### Frontend

```powershell
cd D:\AI-Projects\AI-Automation\frontend
copy .env.example .env.local
npm install
```

`NEXT_PUBLIC_API_URL` defaults to `http://127.0.0.1:8000` (prefer `127.0.0.1` on Windows, not `localhost`).

Also set in `frontend/.env.local` (for local Next.js admin login):

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-strong-password
```

---

## 2. Run locally

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

- Landing: [http://localhost:3000](http://localhost:3000)
- Sign in: [http://localhost:3000/login](http://localhost:3000/login) → workspace `/dashboard`
- Admin (not linked in UI): [http://localhost:3000/admin/login](http://localhost:3000/admin/login)

### Local workflow

1. Sign in (users are created by Admin; no default engineer user)
2. Upload baseline L5X, revised L5X, and governing docs → **Run Analysis**
3. Review findings (Confirm / Dismiss / Needs Investigation)
4. **Export PDF + CSV**

Optional: **Load sample review** on the upload screen for demo findings without upload.

---

## 3. Azure deployment (PowerShell)

One-command deploy from the **monorepo root** (builds images locally with Docker, pushes to ACR, updates Azure Container Apps):

```powershell
cd D:\AI-Projects\AI-Automation
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1
```

### Optional variants

```powershell
# Backend only
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 -BackendOnly

# Frontend only
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 -FrontendOnly
```

### What the script does

1. Registers Azure resource providers if needed  
2. Builds & pushes **backend** + **frontend** Docker images (no ACR Tasks)  
3. Creates/updates Container Apps  
4. Sets backend env from root `.env` (API keys, LLM, embeddings, Qdrant)  
5. Sets frontend env including:
   - `NEXT_PUBLIC_API_URL` (backend URL)
   - `ADMIN_USERNAME` / `ADMIN_PASSWORD` (from root `.env`)
   - `AZURE_STORAGE_CONNECTION_STRING` (auto-created storage for shared `users.csv`)
6. Writes URLs to `deploy-output.txt`

### Prerequisites for deploy

- Docker Desktop running (Linux containers)
- `az login` already done
- Root `.env` filled (API keys + admin credentials)

### After deploy

```powershell
Get-Content .\deploy-output.txt
```

- Open **FrontendUrl** for the landing page  
- Sign in at `/login` (users created via Admin)  
- Admin portal (unlisted): `https://<FrontendUrl>/admin/login`  
- Backend health: `https://<BackendUrl>/api/v1/health`

---

## 4. Optional: local LLM (Ollama)

```powershell
ollama pull llama3.1
ollama serve
```

In `.env`:

```env
LLM_PROVIDER=ollama
LLM_MODEL_NAME=llama3.1
LLM_API_BASE=http://localhost:11434
EMBEDDING_PROVIDER=local
```

Then start backend + frontend as in section 2.

---

## 5. Validation / benchmark scripts

Run from the **project root** after `uv sync`.

```powershell
uv run python backend/tests/test_ingestion.py
uv run python backend/tests/test_diff.py
uv run python backend/tests/test_mapping.py
uv run python backend/tests/test_generation.py
uv run python backend/tests/test_benchmark.py
```

Benchmark options:

```powershell
$env:BENCHMARK_SKIP_LLM = "1"
uv run python backend/tests/test_benchmark.py

$env:BENCHMARK_LLM_LIMIT = "4"
uv run python backend/tests/test_benchmark.py
```

Report output: `sample_data/VALIDATION_REPORT.md`

---

## 6. Manual Docker builds (optional)

```powershell
# Backend API image
docker build -f backend/Dockerfile -t evidra-api .

# Frontend image (bake production API URL at build time)
docker build -f frontend/Dockerfile `
  --build-arg NEXT_PUBLIC_API_URL=https://your-api.azurecontainerapps.io `
  -t evidra-web ./frontend
```

Prefer `.\scripts\deploy-azure.ps1` for full Azure deploy.

---

## 7. Project layout

```
sample_data/           # DC1 benchmark L5X, SOO, ground_truth.json
backend/
  app/
    main.py            # FastAPI entry
    api/               # Routes
    core/              # config.py (pydantic-settings)
    schemas/           # Pydantic models
    services/          # Parse / diff / ingestion / rules
    ai/                # Qdrant, LiteLLM, embeddings
  tests/
frontend/
  src/app/             # Landing, login, dashboard, admin
  src/lib/             # auth (users.csv / Azure blob), API client, export
scripts/
  deploy-azure.ps1     # One-command Azure Container Apps deploy
```

---

## 8. Environment variables (summary)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude LLM (default provider) |
| `OPENAI_API_KEY` | Embeddings / OpenAI LLM fallback |
| `GEMINI_API_KEY` | Gemini LLM/embeddings optional |
| `VOYAGE_API_KEY` | Voyage embeddings optional |
| `LLM_PROVIDER` | `anthropic` \| `openai` \| `gemini` \| … |
| `LLM_MODEL_NAME` | Fast model |
| `LLM_REASONING_MODEL` | Strong reasoning model |
| `EMBEDDING_PROVIDER` | `openai` \| `voyage` \| `gemini` \| `local` |
| `EMBEDDING_MODEL_NAME` | e.g. `text-embedding-3-small` |
| `QDRANT_URL` / `QDRANT_API_KEY` | Vector store |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Frontend admin portal |
| `AZURE_STORAGE_CONNECTION_STRING` | Shared `users.csv` on Azure (auto on deploy) |
| `NEXT_PUBLIC_API_URL` | Frontend → backend URL |

See root `.env.example`, `backend/.env.example`, and `frontend/.env.example`.

---

## Safety note

This product is a **read-only, human-reviewed** audit aid. It never connects to live controllers, never auto-approves a release, and must not be used as operational control code. A qualified engineer must explicitly confirm or dismiss all findings.
