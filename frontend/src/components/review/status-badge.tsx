"use client";

import { Badge } from "@/components/ui/badge";
import type { ReviewStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  Pending: "bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-100",
  Accepted: "bg-emerald-100 text-emerald-800 border-emerald-300 hover:bg-emerald-100",
  Rejected: "bg-red-100 text-red-800 border-red-300 hover:bg-red-100",
  Edited: "bg-amber-100 text-amber-900 border-amber-300 hover:bg-amber-100",
  Unresolved: "bg-violet-100 text-violet-800 border-violet-300 hover:bg-violet-100",
  "Needs Investigation":
    "bg-violet-100 text-violet-800 border-violet-300 hover:bg-violet-100",
};

const STATUS_LABELS: Record<string, string> = {
  Pending: "Pending",
  Accepted: "Confirm Finding",
  Rejected: "Dismiss Finding",
  Edited: "Edited",
  Unresolved: "Unresolved",
  "Needs Investigation": "Needs Investigation",
};

export function StatusBadge({
  status,
  className,
}: {
  status: ReviewStatus;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        STATUS_STYLES[status] ?? STATUS_STYLES.Pending,
        className
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}
