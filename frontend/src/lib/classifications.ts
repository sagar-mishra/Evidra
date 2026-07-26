/**
 * YC demo: findings use ONLY these three classifications.
 * Old change-class labels (Interlocks, Sequences, etc.) must not appear in the UI.
 */

export const FINDING_CLASSIFICATIONS = [
  "Approved change",
  "Suspected regression",
  "Needs review",
] as const;

export type FindingClassification = (typeof FINDING_CLASSIFICATIONS)[number];

/** Map legacy / free-text labels onto the three allowed classifications. */
export function normalizeClassification(raw: string | null | undefined): FindingClassification {
  const value = (raw || "").trim().toLowerCase();
  if (!value) return "Needs review";

  if (
    value === "approved change" ||
    value === "approved" ||
    value.includes("approved change")
  ) {
    return "Approved change";
  }

  if (
    value === "suspected regression" ||
    value === "regression" ||
    value.includes("regression")
  ) {
    return "Suspected regression";
  }

  if (
    value === "needs review" ||
    value.includes("needs review") ||
    value.includes("review")
  ) {
    return "Needs review";
  }

  // Never surface old technical buckets (Interlocks, Modes, Sequences, …)
  return "Needs review";
}

export function classificationStyles(classification: FindingClassification): string {
  switch (classification) {
    case "Approved change":
      return "border-emerald-300 bg-emerald-50 text-emerald-900";
    case "Suspected regression":
      return "border-red-300 bg-red-50 text-red-900";
    case "Needs review":
    default:
      return "border-amber-300 bg-amber-50 text-amber-950";
  }
}
