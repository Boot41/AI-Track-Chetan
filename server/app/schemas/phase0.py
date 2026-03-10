from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QueryType(StrEnum):
    ORIGINAL_EVAL = "original_eval"
    ACQUISITION_EVAL = "acquisition_eval"
    COMPARISON = "comparison"
    FOLLOWUP_WHY_NARRATIVE = "followup_why_narrative"
    FOLLOWUP_WHY_ROI = "followup_why_roi"
    FOLLOWUP_WHY_RISK = "followup_why_risk"
    FOLLOWUP_WHY_CATALOG = "followup_why_catalog"
    SCENARIO_CHANGE_BUDGET = "scenario_change_budget"
    SCENARIO_CHANGE_LOCALIZATION = "scenario_change_localization"
    GENERAL_QUESTION = "general_question"


class AgentTarget(StrEnum):
    DOCUMENT_RETRIEVAL = "document_retrieval"
    NARRATIVE_ANALYSIS = "narrative_analysis"
    ROI_PREDICTION = "roi_prediction"
    RISK_CONTRACT_ANALYSIS = "risk_contract_analysis"
    CATALOG_FIT = "catalog_fit"
    RECOMMENDATION_ENGINE = "recommendation_engine"
    COMPARISON_SYNTHESIS = "comparison_synthesis"


class RecommendationOutcome(StrEnum):
    GREENLIGHT = "GREENLIGHT"
    CONDITIONAL = "CONDITIONAL"
    PASS = "PASS"


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKER = "BLOCKER"


class ScorecardType(StrEnum):
    EVALUATION = "evaluation"
    COMPARISON = "comparison"
    FOLLOWUP = "followup"


class SourceType(StrEnum):
    DOCUMENT_SECTION = "document_section"
    STRUCTURED_METRIC = "structured_metric"
    CONTRACT_FACT = "contract_fact"
    RISK_REGISTER = "risk_register"


class RetrievalMethod(StrEnum):
    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"
    SQL = "sql"
    DERIVED = "derived"


class ComparisonAxis(StrEnum):
    NARRATIVE = "narrative"
    ROI = "roi"
    RISK = "risk"
    CATALOG_FIT = "catalog_fit"


class MetaContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool = False


class RiskFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: RiskSeverity
    summary: str = Field(min_length=1)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    source_type: SourceType
    document_id: str | None = None
    section_id: str | None = None
    snippet: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    retrieval_method: RetrievalMethod
    confidence_score: float = Field(ge=0.0, le=1.0)
    used_by_agent: AgentTarget
    claim_it_supports: str = Field(min_length=1)


class ComparisonOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    query_type: QueryType
    recommendation: RecommendationOutcome | None = None
    estimated_roi: float | None = None
    catalog_fit_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskSeverity | None = None


class ComparisonScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[ComparisonOption] = Field(min_length=2)
    winning_option_id: str | None = None
    comparison_axes: list[ComparisonAxis] = Field(default_factory=list)
    summary: str = Field(min_length=1)

    @field_validator("comparison_axes")
    @classmethod
    def ensure_unique_axes(cls, value: list[ComparisonAxis]) -> list[ComparisonAxis]:
        if len(value) != len(set(value)):
            raise ValueError("comparison_axes must not contain duplicates")
        return value


class EvaluationScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scorecard_type: ScorecardType
    query_type: QueryType
    title: str = Field(min_length=1)
    recommendation: RecommendationOutcome | None = None
    narrative_score: float | None = Field(default=None, ge=0.0, le=100.0)
    projected_completion_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    estimated_roi: float | None = None
    catalog_fit_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskSeverity | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    comparison: ComparisonScorecard | None = None
    focus_area: ComparisonAxis | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "EvaluationScorecard":
        if self.scorecard_type == ScorecardType.COMPARISON and self.comparison is None:
            raise ValueError("comparison scorecard payload is required for comparison scorecards")
        if self.scorecard_type != ScorecardType.COMPARISON and self.comparison is not None:
            raise ValueError("comparison payload is only allowed for comparison scorecards")
        if self.scorecard_type == ScorecardType.FOLLOWUP and self.focus_area is None:
            raise ValueError("followup scorecards require focus_area")
        return self


class PublicResponseContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    scorecard: EvaluationScorecard
    evidence: list[EvidenceItem] = Field(default_factory=list)
    meta: MetaContract


class QueryClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_type: QueryType
    target_agents: list[AgentTarget] = Field(min_length=1)
    reuse_cached_outputs: bool
    requires_recomputation: bool

    @field_validator("target_agents")
    @classmethod
    def ensure_unique_target_agents(cls, value: list[AgentTarget]) -> list[AgentTarget]:
        if len(value) != len(set(value)):
            raise ValueError("target_agents must not contain duplicates")
        return value


class SessionAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: datetime


class ComparisonState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_a: ComparisonOption
    option_b: ComparisonOption
    comparison_scorecard: ComparisonScorecard | None = None
    comparison_axes: list[ComparisonAxis] = Field(default_factory=list)
    active_option: str | None = None

    @model_validator(mode="after")
    def validate_active_option(self) -> "ComparisonState":
        if self.active_option is not None and self.active_option not in {
            self.option_a.option_id,
            self.option_b.option_id,
        }:
            raise ValueError("active_option must match one of the comparison options")
        return self


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pitch_id: str | None = None
    query_type: QueryType | None = None
    narrative_output: SessionAgentOutput | None = None
    roi_output: SessionAgentOutput | None = None
    risk_output: SessionAgentOutput | None = None
    catalog_output: SessionAgentOutput | None = None
    last_scorecard: EvaluationScorecard | None = None
    retrieval_context: list[str] = Field(default_factory=list)
    conversation_intent_history: list[QueryType] = Field(default_factory=list)
    comparison_state: ComparisonState | None = None
    active_option: str | None = None

    @model_validator(mode="after")
    def validate_comparison_state(self) -> "SessionState":
        if self.active_option and self.comparison_state is None:
            raise ValueError("active_option requires comparison_state")
        return self


class TrustedRequestContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    session_id: str = Field(min_length=1)
    chat_message_id: str | None = None
    evaluation_id: str | None = None


class AgentRequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    context: TrustedRequestContext
    session_state: SessionState | None = None


class RecommendationWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative_weight: float = 0.20
    roi_weight: float = 0.30
    risk_weight: float = 0.30
    catalog_fit_weight: float = 0.20

    @model_validator(mode="after")
    def validate_total(self) -> "RecommendationWeights":
        total = (
            self.narrative_weight
            + self.roi_weight
            + self.risk_weight
            + self.catalog_fit_weight
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("recommendation weights must sum to 1.0")
        return self


class RecommendationOverrideRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocker_risk_forces: RecommendationOutcome = RecommendationOutcome.PASS
    high_risk_caps_at: RecommendationOutcome = RecommendationOutcome.CONDITIONAL


class RecommendationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: RecommendationWeights = Field(default_factory=RecommendationWeights)
    overrides: RecommendationOverrideRules = Field(default_factory=RecommendationOverrideRules)


class DocumentFactContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_value: str = Field(min_length=1)
    qualifier: str | None = None
    source_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_by: str = Field(min_length=1)
