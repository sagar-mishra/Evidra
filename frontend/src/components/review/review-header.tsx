"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { exportPackage } from "@/lib/export";
import { computeStats, useReviewStore } from "@/lib/store";
import { AlertOctagon, Download, RefreshCw } from "lucide-react";

export function ReviewHeader() {
  const items = useReviewStore((s) => s.items);
  const projectMeta = useReviewStore((s) => s.projectMeta);
  const releaseRecommendation = useReviewStore((s) => s.releaseRecommendation);
  const clearFindings = useReviewStore((s) => s.clearFindings);
  const stats = useMemo(() => computeStats(items), [items]);

  const title = projectMeta?.project ?? "DC1 Cooling System";
  const dataset =
    projectMeta?.dataset_type ?? "Synthetic controls-release benchmark";
  const rec = releaseRecommendation ?? {
    status: "HOLD FOR ENGINEERING REVIEW",
    reason: "2 critical suspected regressions remain unresolved.",
  };

  return (
    <header className="border-b border-slate-200 bg-slate-900 text-slate-100">
      {/* Release recommendation banner */}
      <div className="flex flex-wrap items-start gap-3 border-b border-amber-700/40 bg-amber-950/80 px-4 py-2.5">
        <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
        <div className="min-w-0">
          <p className="text-sm font-semibold tracking-tight text-amber-100">
            Release recommendation: {rec.status}
          </p>
          <p className="text-[12px] text-amber-200/90">Reason: {rec.reason}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
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
          <p className="mt-1 truncate text-[11px] text-slate-400">
            Project: {title} | Dataset type: {dataset}
          </p>
          {projectMeta && (
            <p className="mt-0.5 truncate text-[10px] text-slate-500">
              {projectMeta.controller} · {projectMeta.baseline} →{" "}
              {projectMeta.revised}
              {projectMeta.soo ? ` · ${projectMeta.soo}` : ""}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="hidden text-right text-[11px] text-slate-300 sm:block">
            <div>
              {stats.accepted} confirmed · {stats.rejected} dismissed ·{" "}
              {stats.pending + stats.edited + stats.unresolved} open
            </div>
            <div className="text-slate-500">
              Human review required — no autonomous approval
            </div>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-slate-600 bg-transparent text-slate-100 hover:bg-slate-800"
            onClick={() => clearFindings()}
          >
            <RefreshCw className="mr-1.5 h-4 w-4" />
            New analysis
          </Button>
          <Button
            size="sm"
            className="bg-emerald-500 text-slate-950 hover:bg-emerald-400"
            onClick={() =>
              exportPackage(items, {
                projectName: projectMeta?.project,
                controller: projectMeta?.controller,
                baseline: projectMeta?.baseline,
                revised: projectMeta?.revised,
                soo: projectMeta?.soo,
              })
            }
            disabled={items.length === 0}
          >
            <Download className="mr-1.5 h-4 w-4" />
            Export PDF + CSV
          </Button>
        </div>
      </div>
    </header>
  );
}
