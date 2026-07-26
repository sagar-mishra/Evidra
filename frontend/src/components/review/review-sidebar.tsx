"use client";

import { useMemo } from "react";
import { ClassificationBadge } from "@/components/review/classification-badge";
import { StatusBadge } from "@/components/review/status-badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { normalizeClassification } from "@/lib/classifications";
import { computeStats, filterItems, useReviewStore } from "@/lib/store";
import type { ReviewStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AlertTriangle, Filter, ListChecks } from "lucide-react";

const FILTERS: Array<ReviewStatus | "All"> = [
  "All",
  "Pending",
  "Accepted",
  "Rejected",
  "Edited",
  "Unresolved",
];

export function ReviewSidebar() {
  const allItems = useReviewStore((s) => s.items);
  const selectedItemId = useReviewStore((s) => s.selectedItemId);
  const selectItem = useReviewStore((s) => s.selectItem);
  const filterStatus = useReviewStore((s) => s.filterStatus);
  const setFilterStatus = useReviewStore((s) => s.setFilterStatus);

  const items = useMemo(
    () => filterItems(allItems, filterStatus),
    [allItems, filterStatus]
  );
  const stats = useMemo(() => computeStats(allItems), [allItems]);

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2">
          <ListChecks className="h-5 w-5 text-slate-700" />
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Review Queue</h2>
            <p className="text-xs text-slate-500">{stats.total} findings</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
          <Stat label="Pending" value={stats.pending} />
          <Stat label="Confirmed" value={stats.accepted} />
          <Stat label="Dismissed" value={stats.rejected} />
          <Stat label="Edited" value={stats.edited} />
          <Stat label="Investigate" value={stats.unresolved} />
          <Stat label="Total" value={stats.total} />
        </div>

        <div>
          <div className="mb-1.5 flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            <Filter className="h-3 w-3" />
            Filter
          </div>
          <div className="flex flex-wrap gap-1">
            {FILTERS.map((f) => (
              <Button
                key={f}
                size="sm"
                variant={filterStatus === f ? "default" : "outline"}
                className="h-7 px-2 text-[11px]"
                onClick={() => setFilterStatus(f)}
              >
                {f}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <Separator />

      <ScrollArea className="flex-1">
        <div className="space-y-1.5 p-2">
          {items.length === 0 && (
            <p className="p-3 text-center text-xs text-slate-500">
              No items match this filter.
            </p>
          )}
          {items.map((item) => {
            const selected = item.id === selectedItemId;
            const classification = normalizeClassification(item.classification);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => selectItem(item.id)}
                className={cn(
                  "w-full rounded-lg border p-3 text-left transition",
                  selected
                    ? "border-slate-900 bg-white shadow-sm"
                    : "border-transparent bg-transparent hover:border-slate-200 hover:bg-white"
                )}
              >
                <div className="mb-1.5 flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-900">
                    {item.id}
                  </span>
                  <StatusBadge status={item.status} />
                </div>

                {/* Exclusive finding classification — not Interlocks/Sequences/etc. */}
                <div className="mb-2">
                  <ClassificationBadge classification={classification} />
                </div>

                <p className="line-clamp-2 text-xs font-medium text-slate-800">
                  {item.test_plan.title}
                </p>
                <p className="mt-1 line-clamp-1 font-mono text-[10px] text-slate-500">
                  {item.location}
                </p>
                {(item.severity === "Critical" || item.severity === "High") && (
                  <div className="mt-2 inline-flex items-center gap-0.5 text-[10px] font-medium text-red-700">
                    <AlertTriangle className="h-3 w-3" />
                    {item.severity}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </ScrollArea>

      <div className="border-t border-slate-200 p-3 text-[10px] text-slate-500">
        Showing {items.length} of {allItems.length} items
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-1 py-1.5">
      <div className="text-sm font-semibold text-slate-900">{value}</div>
      <div className="text-slate-500">{label}</div>
    </div>
  );
}
