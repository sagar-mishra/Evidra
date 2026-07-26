"use client";

import {
  classificationStyles,
  normalizeClassification,
  type FindingClassification,
} from "@/lib/classifications";
import { cn } from "@/lib/utils";

export function ClassificationBadge({
  classification,
  className,
}: {
  classification: string | FindingClassification | null | undefined;
  className?: string;
}) {
  const value = normalizeClassification(classification);
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold leading-tight",
        classificationStyles(value),
        className
      )}
      title={value}
    >
      {value}
    </span>
  );
}
