"use client";

import { useMemo } from "react";
import { RequireUserSession } from "@/components/auth/require-user-session";
import { ProductNavActions } from "@/components/product/product-nav-actions";
import { UploadModal } from "@/components/UploadModal";
import { DiffPane } from "@/components/review/diff-pane";
import { ReviewHeader } from "@/components/review/review-header";
import { ReviewSidebar } from "@/components/review/review-sidebar";
import { SummaryRibbon } from "@/components/review/summary-ribbon";
import { TestPlanPane } from "@/components/review/test-plan-pane";
import { Button } from "@/components/ui/button";
import { useReviewStore } from "@/lib/store";
import { AlertCircle } from "lucide-react";

/**
 * 3-pane human review dashboard (authenticated app).
 *
 * Empty store → UploadModal (baseline L5X, revised L5X, SOO).
 * After analysis → Review Queue | L5X Diff + SOO | AI Test Plan.
 */
export default function ReviewWorkspacePage() {
  const items = useReviewStore((s) => s.items);
  const selectedItemId = useReviewStore((s) => s.selectedItemId);
  const showUpload = useReviewStore((s) => s.showUpload);
  const analyzing = useReviewStore((s) => s.analyzing);
  const error = useReviewStore((s) => s.error);
  const clearFindings = useReviewStore((s) => s.clearFindings);

  const selectedItem = useMemo(
    () => items.find((i) => i.id === selectedItemId) ?? null,
    [items, selectedItemId]
  );

  const showUploadView = showUpload || items.length === 0 || analyzing;

  return (
    <RequireUserSession>
      <div className="flex h-screen min-h-0 flex-col bg-slate-100 text-slate-900">
        {!showUploadView && (
          <>
            <ReviewHeader />
            <SummaryRibbon />
          </>
        )}

        {error && !analyzing && !showUploadView && (
          <div className="flex items-center justify-between gap-3 border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="border-red-300"
              onClick={() => clearFindings()}
            >
              New analysis
            </Button>
          </div>
        )}

        {showUploadView ? (
          <>
            <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-900 px-4 py-3 text-slate-100">
              <div className="flex min-w-0 items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/logo.png"
                  alt="Evidra Logo"
                  className="h-9 w-auto object-contain"
                />
                <span className="text-xl font-bold tracking-tight text-white">
                  Evidra
                </span>
                <span className="hidden text-slate-600 sm:inline" aria-hidden>
                  |
                </span>
                <p className="min-w-0 truncate text-[11px] text-slate-400 sm:text-xs">
                  Every change, proven before production.
                </p>
              </div>
              <ProductNavActions variant="dark" />
            </header>
            <UploadModal />
          </>
        ) : (
          <div className="flex min-h-0 flex-1">
            <ReviewSidebar />

            <main className="flex min-h-0 min-w-0 flex-1 flex-col">
              {!selectedItem ? (
                <div className="flex flex-1 items-center justify-center p-8 text-sm text-slate-500">
                  Select a review item from the queue to begin human review.
                </div>
              ) : (
                <div className="grid min-h-0 flex-1 overflow-hidden lg:grid-cols-2">
                  <section className="relative min-h-0 overflow-hidden border-b border-slate-200 bg-slate-50 lg:border-b-0 lg:border-r">
                    <DiffPane item={selectedItem} />
                  </section>
                  <section className="relative min-h-0 overflow-hidden bg-white">
                    <TestPlanPane item={selectedItem} />
                  </section>
                </div>
              )}
            </main>
          </div>
        )}
      </div>
    </RequireUserSession>
  );
}
