"use client";

import { useReviewStore } from "@/lib/store";

/**
 * YC demo metrics ribbon — three primary counts.
 */
export function SummaryRibbon() {
  const summary = useReviewStore((s) => s.summary);
  if (!summary) return null;

  const metrics = [
    {
      label: "Code changes analyzed",
      value: summary.changes_analyzed,
      emphasize: false,
    },
    {
      label: "Behavioral findings",
      value: summary.behavioral_findings ?? summary.total_findings,
      emphasize: false,
    },
    {
      label: "Regression tests required",
      value:
        summary.regression_tests_required ??
        summary.regression_tests_generated ??
        summary.total_findings,
      emphasize: summary.critical_findings > 0,
    },
  ];

  return (
    <div className="border-b border-slate-800 bg-slate-950 text-slate-100">
      <div className="grid grid-cols-1 gap-px sm:grid-cols-3">
        {metrics.map(({ label, value, emphasize }) => (
          <div
            key={label}
            className="flex min-w-0 flex-col justify-center px-3 py-2.5 sm:px-4"
          >
            <span className="truncate text-[10px] font-medium uppercase tracking-wide text-slate-400">
              {label}
            </span>
            <span
              className={
                emphasize
                  ? "text-lg font-semibold tabular-nums text-red-400"
                  : "text-lg font-semibold tabular-nums text-slate-50"
              }
            >
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
