/**
 * Typed fetch client for the Evidra FastAPI backend.
 */

import type {
  AnalyzeResponse,
  GenerateTestRequest,
  GenerateTestResponse,
  MockFindingsResponse,
  ReviewItem,
} from "@/lib/types";

/**
 * Backend origin for browser fetch calls.
 * Prefer NEXT_PUBLIC_API_URL (Azure / production); fall back to local FastAPI.
 * NEXT_PUBLIC_API_BASE is kept as a legacy alias.
 *
 * Use 127.0.0.1 (not localhost) on Windows: `localhost` often resolves to ::1
 * and can hit WSL/Docker on :8000 instead of the local uvicorn process.
 */
export const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function formatDetail(data: unknown, fallback: string): string {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) =>
          typeof d === "object" && d && "msg" in d
            ? String((d as { msg: unknown }).msg)
            : JSON.stringify(d)
        )
        .join("; ");
    }
    if (detail != null) return String(detail);
  }
  return fallback;
}

function networkErrorMessage(url: string, err: unknown): string {
  const cause =
    err instanceof Error
      ? err.message
      : typeof err === "string"
        ? err
        : "Failed to fetch";
  return (
    `Network error calling ${url} (${cause}). ` +
    `Confirm FastAPI is up: curl http://127.0.0.1:8000/api/v1/health. ` +
    `On Windows prefer NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 (not localhost).`
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        // Do not set Content-Type for FormData — browser sets multipart boundary.
        ...(init?.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...init?.headers,
      },
    });
  } catch (err) {
    throw new ApiError(networkErrorMessage(url, err), 0, err);
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      formatDetail(data, response.statusText || `HTTP ${response.status}`),
      response.status,
      data
    );
  }

  return data as T;
}

/** GET /api/v1/health */
export async function fetchHealth(): Promise<{ status: string; service: string }> {
  return request("/api/v1/health");
}

/**
 * GET /api/v1/mock-findings
 * Temporary mock review queue (no file upload).
 */
export async function fetchMockFindings(): Promise<MockFindingsResponse> {
  return request<MockFindingsResponse>("/api/v1/mock-findings");
}

/** Convenience: just the ReviewItem list from mock-findings. */
export async function fetchMockReviewItems(): Promise<ReviewItem[]> {
  const res = await fetchMockFindings();
  return res.items;
}

export interface AnalyzeUploadFiles {
  baseline_l5x: File;
  revised_l5x: File;
  /** One or more governing documents (PDF / DOCX / XLSX / CSV) */
  governing_docs: File[];
  /** @deprecated prefer governing_docs */
  soo_pdf?: File;
}

/**
 * POST /api/v1/analyze
 * Multipart upload of baseline L5X, revised L5X, and governing docs.
 */
export async function analyzeProject(
  files: AnalyzeUploadFiles
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("baseline_l5x", files.baseline_l5x);
  form.append("revised_l5x", files.revised_l5x);
  const docs =
    files.governing_docs?.length > 0
      ? files.governing_docs
      : files.soo_pdf
        ? [files.soo_pdf]
        : [];
  for (const doc of docs) {
    form.append("governing_docs", doc);
  }
  // Back-compat single field
  if (files.soo_pdf) {
    form.append("soo_pdf", files.soo_pdf);
  }

  return request<AnalyzeResponse>("/api/v1/analyze", {
    method: "POST",
    body: form,
  });
}

/** POST /api/v1/generate-test */
export async function generateRegressionTest(
  body: GenerateTestRequest
): Promise<GenerateTestResponse> {
  return request<GenerateTestResponse>("/api/v1/generate-test", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
