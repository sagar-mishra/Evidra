/**
 * Frontend domain types — wire-compatible with backend Pydantic schemas.
 */

export type ReviewStatus =
  | "Pending"
  | "Accepted"
  | "Rejected"
  | "Edited"
  | "Unresolved"
  | "Needs Investigation";

/** Exclusive finding classifications for the YC demo UI */
export type FindingClassification =
  | "Approved change"
  | "Suspected regression"
  | "Needs review";

export type Severity = "Critical" | "High" | "Medium" | "Low";

export type PredictedTestOutcome = "PASS" | "FAIL" | "UNKNOWN";

export type EngineeringDisposition =
  | "CONFIRM FINDING"
  | "DISMISS"
  | "NEEDS INVESTIGATION";

export type UncertaintyLevel =
  | "Verified"
  | "High confidence"
  | "Probable"
  | "Unknown";

export interface TestStep {
  step_number: number;
  action: string;
  observation?: string | null;
}

export interface RegressionTestPlan {
  test_id: string;
  title: string;
  affected_equipment?: string[];
  category?: string;
  change_class?: string | null;
  related_tags?: string[];
  governing_requirement?: string;
  change_summary?: string;
  purpose?: string;
  prerequisites: string[];
  test_steps: TestStep[];
  expected_result: string;
  flag_rationale?: string;
  evidence_to_capture?: string[];
  safety_notes?: string[];
}

export interface LogicAnnotation {
  token: string;
  change: "added" | "removed" | string;
  note: string;
}

export interface ReviewItem {
  id: string;
  status: ReviewStatus;
  change_class?: string;
  severity: Severity;
  location: string;
  equipment: string | null;
  tag_name: string | null;
  baseline_evidence: string;
  revised_evidence: string;
  requirement_id: string;
  requirement_text: string;
  requirement_source: string;
  soo_page_or_section: string;
  classification: FindingClassification | string;
  test_plan: RegressionTestPlan;
  original_test_plan: RegressionTestPlan;
  reviewer_notes: string;
  updated_at: string;

  // 5 mandatory behavioral fields
  required_behavior?: string;
  verified_code_change?: string;
  predicted_revised_behavior?: string;
  test_pass_condition?: string;
  predicted_test_outcome?: PredictedTestOutcome;

  engineering_disposition?: EngineeringDisposition | string;
  uncertainty?: UncertaintyLevel | string;

  document_name?: string;
  document_revision?: string;
  requirement_page?: number;
  requirement_section?: string;

  trigger_equipment?: string[];
  affected_equipment?: string[];
  affected_output?: string;
  system?: string;
  routine?: string;
  rung?: string | null;
  logic_annotations?: LogicAnnotation[];
}

/** Dashboard ribbon metrics */
export interface FindingsSummary {
  changes_analyzed: number;
  requirements_affected?: number;
  total_findings: number;
  critical_findings: number;
  regression_tests_generated?: number;
  behavioral_findings?: number;
  regression_tests_required?: number;
}

export interface ReleaseRecommendation {
  status: string;
  reason: string;
}

export interface MockFindingsResponse {
  items: ReviewItem[];
  count: number;
  summary: FindingsSummary;
  source: "mock";
  project: string;
  dataset_type?: string;
  controller: string;
  baseline: string;
  revised: string;
  soo?: string | null;
  release_recommendation?: ReleaseRecommendation;
}

export interface AnalyzeResponse {
  items: ReviewItem[];
  count: number;
  summary: FindingsSummary;
  source: "pipeline";
  project: string;
  dataset_type?: string;
  controller: string;
  baseline: string;
  revised: string;
  soo?: string | null;
  governing_docs?: string[] | null;
  diff_summary?: {
    total_changes?: number;
    tag_changes?: number;
    rung_changes?: number;
  } | null;
  soo_block_count?: number | null;
  message?: string | null;
  release_recommendation?: ReleaseRecommendation | null;
}

export interface ReviewStats {
  total: number;
  pending: number;
  accepted: number;
  rejected: number;
  edited: number;
  unresolved: number;
}

export interface GenerateTestRequest {
  tag_change: string;
  requirement: string;
  affected_equipment?: string[] | null;
  related_tags?: string[] | null;
  category_hint?: string | null;
}

export interface GenerateTestResponse {
  test_plan: RegressionTestPlan;
  model: string;
  api_base: string;
}
