export type QueryType =
  | "original_eval"
  | "acquisition_eval"
  | "comparison"
  | "followup_why_narrative"
  | "followup_why_roi"
  | "followup_why_risk"
  | "followup_why_catalog"
  | "scenario_change_budget"
  | "scenario_change_localization"
  | "general_question";

export type ScorecardType = "evaluation" | "comparison" | "followup";
export type Recommendation = "GREENLIGHT" | "CONDITIONAL" | "PASS";
export type RiskSeverity = "LOW" | "MEDIUM" | "HIGH" | "BLOCKER";
export type ComparisonAxis = "narrative" | "roi" | "risk" | "catalog_fit";

export interface RiskFlag {
  code: string;
  severity: RiskSeverity;
  summary: string;
}

export interface ComparisonOption {
  option_id: string;
  label: string;
  query_type: QueryType;
  recommendation?: Recommendation | null;
  estimated_roi?: number | null;
  catalog_fit_score?: number | null;
  risk_level?: RiskSeverity | null;
}

export interface ComparisonScorecard {
  options: ComparisonOption[];
  winning_option_id?: string | null;
  comparison_axes: ComparisonAxis[];
  summary: string;
}

export interface EvaluationScorecard {
  scorecard_type: ScorecardType;
  query_type: QueryType;
  title: string;
  recommendation?: Recommendation | null;
  narrative_score?: number | null;
  projected_completion_rate?: number | null;
  estimated_roi?: number | null;
  catalog_fit_score?: number | null;
  risk_level?: RiskSeverity | null;
  risk_flags: RiskFlag[];
  comparison?: ComparisonScorecard | null;
  focus_area?: ComparisonAxis | null;
}

export interface EvidenceItem {
  evidence_id: string;
  source_type: string;
  document_id?: string | null;
  section_id?: string | null;
  snippet: string;
  source_reference: string;
  retrieval_method: string;
  confidence_score: number;
  used_by_agent: string;
  claim_it_supports: string;
}

export interface MetaContract {
  warnings: string[];
  confidence: number;
  review_required: boolean;
}

export interface PublicResponseContract {
  answer: string;
  scorecard: EvaluationScorecard;
  evidence: EvidenceItem[];
  meta: MetaContract;
}
