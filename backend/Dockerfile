# Release Assurance — FastAPI backend
# Build from monorepo root:
#   docker build -f backend/Dockerfile -t release-assurance-api .
#
# Run:
#   docker run --rm -p 8000:8000 --env-file .env release-assurance-api

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# System deps for lxml / WeasyPrint-adjacent builds if needed later
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Project metadata + lock (monorepo root context)
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend

# Install project into the image environment (maps backend/app → import app)
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Azure Container Apps / local Docker listen on all interfaces
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
