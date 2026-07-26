/**
 * @deprecated Static demo data removed — the UI now loads findings from
 * FastAPI `GET /api/v1/mock-findings` via `useReviewStore.loadMockFindings()`.
 *
 * Kept as a thin meta constant for optional offline labels only.
 */

export const PROJECT_META = {
  productName: "Evidra",
  tagline: "Every change, proven before production.",
  projectName: "DC1 Cooling System",
  controller: "DC1_MEP_PLC01",
  baseline: "DC1_Cooling_Baseline_RevA.L5X",
  revised: "DC1_Cooling_Revised_RevB.L5X",
  soo: "DC1_Cooling_SOO_RevB",
};
