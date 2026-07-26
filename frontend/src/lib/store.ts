/**
 * Zustand store for human review workflow state.
 */

import { create } from "zustand";
import {
  analyzeProject,
  fetchMockFindings,
  ApiError,
  type AnalyzeUploadFiles,
} from "@/lib/api";
import { normalizeClassification } from "@/lib/classifications";
import type {
  AnalyzeResponse,
  FindingsSummary,
  MockFindingsResponse,
  RegressionTestPlan,
  ReleaseRecommendation,
  ReviewItem,
  ReviewStats,
  ReviewStatus,
} from "@/lib/types";

interface ProjectMeta {
  project: string;
  controller: string;
  baseline: string;
  revised: string;
  soo?: string;
  dataset_type?: string;
}

interface ReviewState {
  items: ReviewItem[];
  selectedItemId: string | null;
  filterStatus: ReviewStatus | "All";
  loading: boolean;
  analyzing: boolean;
  analysisStage: string | null;
  error: string | null;
  hydrated: boolean;
  projectMeta: ProjectMeta | null;
  showUpload: boolean;
  /** Compact dashboard metrics from analyze / mock-findings */
  summary: FindingsSummary | null;
  releaseRecommendation: ReleaseRecommendation | null;

  loadMockFindings: () => Promise<void>;
  runAnalysis: (files: AnalyzeUploadFiles) => Promise<void>;
  clearFindings: () => void;
  setShowUpload: (show: boolean) => void;
  setItems: (items: ReviewItem[]) => void;
  selectItem: (id: string | null) => void;
  setFilterStatus: (status: ReviewStatus | "All") => void;
  setStatus: (id: string, status: ReviewStatus) => void;
  acceptItem: (id: string) => void;
  rejectItem: (id: string) => void;
  markUnresolved: (id: string) => void;
  confirmFinding: (id: string) => void;
  dismissFinding: (id: string) => void;
  needsInvestigation: (id: string) => void;
  updateTestPlan: (id: string, plan: RegressionTestPlan) => void;
  updateReviewerNotes: (id: string, notes: string) => void;
  resetItem: (id: string) => void;

  accept: (id: string) => void;
  reject: (id: string) => void;
  hydrate: (items: ReviewItem[]) => void;
}

export function computeStats(items: ReviewItem[]): ReviewStats {
  const stats: ReviewStats = {
    total: items.length,
    pending: 0,
    accepted: 0,
    rejected: 0,
    edited: 0,
    unresolved: 0,
  };
  for (const item of items) {
    switch (item.status) {
      case "Pending":
        stats.pending += 1;
        break;
      case "Accepted":
        stats.accepted += 1;
        break;
      case "Rejected":
        stats.rejected += 1;
        break;
      case "Edited":
        stats.edited += 1;
        break;
      case "Unresolved":
      case "Needs Investigation":
        stats.unresolved += 1;
        break;
    }
  }
  return stats;
}

export function filterItems(
  items: ReviewItem[],
  filterStatus: ReviewStatus | "All"
): ReviewItem[] {
  if (filterStatus === "All") return items;
  return items.filter((i) => i.status === filterStatus);
}

function touch(item: ReviewItem, patch: Partial<ReviewItem>): ReviewItem {
  return {
    ...item,
    ...patch,
    updated_at: new Date().toISOString(),
  };
}

/** Normalize API items so UI only ever sees the three allowed classifications. */
function normalizeReviewItems(items: ReviewItem[]): ReviewItem[] {
  return items.map((item) => ({
    ...item,
    classification: normalizeClassification(item.classification),
  }));
}

function applyFindingsPayload(
  res: MockFindingsResponse | AnalyzeResponse
): Partial<ReviewState> {
  const items = normalizeReviewItems(res.items);
  const rec =
    "release_recommendation" in res && res.release_recommendation
      ? res.release_recommendation
      : {
          status: "HOLD FOR ENGINEERING REVIEW",
          reason: "2 critical suspected regressions remain unresolved.",
        };
  return {
    items,
    selectedItemId: items[0]?.id ?? null,
    summary: res.summary,
    releaseRecommendation: rec,
    projectMeta: {
      project: res.project,
      controller: res.controller,
      baseline: res.baseline,
      revised: res.revised,
      soo: "soo" in res ? res.soo ?? undefined : undefined,
      dataset_type:
        "dataset_type" in res && res.dataset_type
          ? res.dataset_type
          : "Synthetic controls-release benchmark",
    },
    loading: false,
    analyzing: false,
    analysisStage: null,
    hydrated: true,
    showUpload: false,
    error: null,
  };
}

export const useReviewStore = create<ReviewState>((set, get) => ({
  items: [],
  selectedItemId: null,
  filterStatus: "All",
  loading: false,
  analyzing: false,
  analysisStage: null,
  error: null,
  hydrated: false,
  projectMeta: null,
  showUpload: true,
  summary: null,
  releaseRecommendation: null,

  loadMockFindings: async () => {
    set({ loading: true, error: null, analysisStage: "Loading demo findings…" });
    try {
      const res = await fetchMockFindings();
      set(applyFindingsPayload(res));
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Failed to load findings";
      set({
        loading: false,
        analyzing: false,
        analysisStage: null,
        error: message,
        hydrated: false,
      });
    }
  },

  runAnalysis: async (files) => {
    set({
      analyzing: true,
      loading: true,
      error: null,
      analysisStage: "Uploading files to backend…",
    });

    // Client-side stage hints (server is synchronous; stages advance around the request)
    const stages = [
      "Uploading project files…",
      "Comparing PLC programs…",
      "Linking changes to requirements…",
      "Applying industrial instruction rules…",
      "Drafting focused regression tests…",
    ];
    let stageIndex = 0;
    const timer = setInterval(() => {
      stageIndex = Math.min(stageIndex + 1, stages.length - 1);
      if (get().analyzing) {
        set({ analysisStage: stages[stageIndex] });
      }
    }, 4000);

    try {
      set({ analysisStage: stages[1] });
      const res = await analyzeProject(files);
      clearInterval(timer);
      set(applyFindingsPayload(res));
    } catch (err) {
      clearInterval(timer);
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Analysis failed";
      set({
        loading: false,
        analyzing: false,
        analysisStage: null,
        error: message,
      });
      throw err;
    }
  },

  clearFindings: () =>
    set({
      items: [],
      selectedItemId: null,
      hydrated: false,
      projectMeta: null,
      showUpload: true,
      error: null,
      analysisStage: null,
      analyzing: false,
      loading: false,
      summary: null,
      releaseRecommendation: null,
    }),

  setShowUpload: (show) => set({ showUpload: show }),

  setItems: (items) =>
    set({
      items,
      selectedItemId: items[0]?.id ?? null,
      hydrated: true,
      showUpload: items.length === 0,
    }),

  selectItem: (id) => set({ selectedItemId: id }),

  setFilterStatus: (status) => set({ filterStatus: status }),

  setStatus: (id, status) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? touch(item, { status }) : item
      ),
    })),

  acceptItem: (id) => get().setStatus(id, "Accepted"),
  rejectItem: (id) => get().setStatus(id, "Rejected"),
  markUnresolved: (id) => get().setStatus(id, "Unresolved"),
  // YC demo disposition labels → wire statuses
  confirmFinding: (id) => get().setStatus(id, "Accepted"),
  dismissFinding: (id) => get().setStatus(id, "Rejected"),
  needsInvestigation: (id) => get().setStatus(id, "Needs Investigation"),

  accept: (id) => get().acceptItem(id),
  reject: (id) => get().rejectItem(id),

  updateTestPlan: (id, plan) =>
    set((state) => ({
      items: state.items.map((item) => {
        if (item.id !== id) return item;
        return touch(item, {
          test_plan: plan,
          status: "Edited",
        });
      }),
    })),

  updateReviewerNotes: (id, notes) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? touch(item, { reviewer_notes: notes }) : item
      ),
    })),

  resetItem: (id) =>
    set((state) => ({
      items: state.items.map((item) => {
        if (item.id !== id) return item;
        return touch(item, {
          test_plan: structuredClone(item.original_test_plan),
          status: "Pending",
          reviewer_notes: "",
        });
      }),
    })),

  hydrate: (items) => get().setItems(items),
}));
