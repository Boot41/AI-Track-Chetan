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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function assertRiskFlag(flag: unknown): asserts flag is RiskFlag {
  if (!isRecord(flag)) {
    throw new Error("Invalid scorecard risk flag");
  }
  if (
    typeof flag.code !== "string" ||
    typeof flag.severity !== "string" ||
    typeof flag.summary !== "string"
  ) {
    throw new Error("Invalid scorecard risk flag");
  }
}

function assertComparisonOption(option: unknown): asserts option is ComparisonOption {
  if (!isRecord(option)) {
    throw new Error("Invalid comparison option");
  }
  if (
    typeof option.option_id !== "string" ||
    typeof option.label !== "string" ||
    typeof option.query_type !== "string"
  ) {
    throw new Error("Invalid comparison option");
  }
}

function assertComparisonScorecard(comparison: unknown): asserts comparison is ComparisonScorecard {
  if (!isRecord(comparison)) {
    throw new Error("Invalid comparison scorecard");
  }
  if (!Array.isArray(comparison.options) || !Array.isArray(comparison.comparison_axes)) {
    throw new Error("Invalid comparison scorecard");
  }
  comparison.options.forEach(assertComparisonOption);
  if (typeof comparison.summary !== "string") {
    throw new Error("Invalid comparison scorecard");
  }
}

function assertScorecard(scorecard: unknown): asserts scorecard is EvaluationScorecard {
  if (!isRecord(scorecard)) {
    throw new Error("Invalid response scorecard");
  }
  if (
    typeof scorecard.scorecard_type !== "string" ||
    typeof scorecard.query_type !== "string" ||
    typeof scorecard.title !== "string" ||
    !Array.isArray(scorecard.risk_flags)
  ) {
    throw new Error("Invalid response scorecard");
  }
  scorecard.risk_flags.forEach(assertRiskFlag);
  if (scorecard.comparison !== undefined && scorecard.comparison !== null) {
    assertComparisonScorecard(scorecard.comparison);
  }
}

function assertEvidenceItem(item: unknown): asserts item is EvidenceItem {
  if (!isRecord(item)) {
    throw new Error("Invalid response evidence");
  }
  if (
    typeof item.evidence_id !== "string" ||
    typeof item.source_type !== "string" ||
    typeof item.snippet !== "string" ||
    typeof item.source_reference !== "string" ||
    typeof item.retrieval_method !== "string" ||
    typeof item.confidence_score !== "number" ||
    typeof item.used_by_agent !== "string" ||
    typeof item.claim_it_supports !== "string"
  ) {
    throw new Error("Invalid response evidence");
  }
}

function assertPublicMeta(meta: unknown): asserts meta is MetaContract {
  if (!isRecord(meta)) {
    throw new Error("Invalid response meta");
  }
  if (
    !Array.isArray(meta.warnings) ||
    typeof meta.confidence !== "number" ||
    meta.confidence < 0 ||
    meta.confidence > 1 ||
    typeof meta.review_required !== "boolean"
  ) {
    throw new Error("Invalid response meta");
  }
}

export function parsePublicResponseContract(value: unknown): PublicResponseContract {
  if (!isRecord(value)) {
    throw new Error("Invalid response payload");
  }
  if (typeof value.answer !== "string") {
    throw new Error("Invalid response answer");
  }
  if (!Array.isArray(value.evidence)) {
    throw new Error("Invalid response evidence");
  }
  assertScorecard(value.scorecard);
  value.evidence.forEach(assertEvidenceItem);
  assertPublicMeta(value.meta);
  return value as unknown as PublicResponseContract;
}
