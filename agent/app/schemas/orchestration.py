from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent.app.schemas.ingestion import DocumentType, RetrievalMethod
from agent.app.schemas.retrieval import RetrievalCandidate


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


class ToolName(StrEnum):
    SQL_RETRIEVAL = "sql_retrieval"
    HYBRID_DOCUMENT_RETRIEVAL = "hybrid_document_retrieval"
    CLAUSE_EXTRACTION = "clause_extraction"
    NARRATIVE_FEATURE_EXTRACTION = "narrative_feature_extraction"
    EVIDENCE_PACKAGING = "evidence_packaging"


class CachedOutputName(StrEnum):
    NARRATIVE = "narrative_output"
    ROI = "roi_output"
    RISK = "risk_output"
    CATALOG = "catalog_output"


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


class ComparisonOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    query_type: QueryType


class ComparisonState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_a: ComparisonOption
    option_b: ComparisonOption
    comparison_axes: list[str] = Field(default_factory=list)
    active_option: str | None = None

    @model_validator(mode="after")
    def validate_active_option(self) -> ComparisonState:
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
    retrieval_context: list[str] = Field(default_factory=list)
    conversation_intent_history: list[QueryType] = Field(default_factory=list)
    comparison_state: ComparisonState | None = None
    active_option: str | None = None

    @model_validator(mode="after")
    def validate_comparison_state(self) -> SessionState:
        if self.active_option is not None and self.comparison_state is None:
            raise ValueError("active_option requires comparison_state")
        if (
            self.comparison_state is not None
            and self.comparison_state.active_option is not None
            and self.active_option is not None
            and self.active_option != self.comparison_state.active_option
        ):
            raise ValueError("active_option must match comparison_state.active_option")
        return self


class TrustedRequestContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    session_id: str = Field(min_length=1)
    chat_message_id: str | None = None
    evaluation_id: str | None = None


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    context: TrustedRequestContext
    session_state: SessionState | None = None


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: ToolName
    cached: bool = False
    details: dict[str, object] = Field(default_factory=dict)


class AgentInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: AgentTarget
    cached: bool = False
    details: dict[str, object] = Field(default_factory=dict)


class RouteDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_type: QueryType
    target_agents: list[AgentTarget] = Field(min_length=1)
    reusable_outputs: list[CachedOutputName] = Field(default_factory=list)
    recompute_outputs: list[CachedOutputName] = Field(default_factory=list)
    comparison_enabled: bool = False
    downstream_handoffs: list[AgentTarget] = Field(default_factory=list)


class RoutePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_type: QueryType
    agent_sequence: list[AgentTarget] = Field(min_length=1)
    cached_outputs_to_use: list[CachedOutputName] = Field(default_factory=list)
    outputs_to_recompute: list[CachedOutputName] = Field(default_factory=list)
    active_option_id: str | None = None
    evaluate_all_comparison_options: bool = False
    support_agents: list[AgentTarget] = Field(default_factory=list)


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str | None = None
    section_id: str | None = None
    snippet: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    retrieval_method: RetrievalMethod
    confidence_score: float = Field(ge=0.0, le=1.0)
    used_by_agent: AgentTarget
    claim_it_supports: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class SqlMetricRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_key: str = Field(min_length=1)
    value: str | float | int | bool
    source_table: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)


class SqlRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pitch_id: str | None = None
    metric_keys: list[str] = Field(default_factory=list)
    active_option_id: str | None = None


class SqlRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[SqlMetricRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HybridDocumentRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=1)
    content_ids: list[str] = Field(default_factory=list)
    document_types: list[DocumentType] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=25)


class HybridDocumentRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[RetrievalCandidate] = Field(default_factory=list)


class ClauseMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    clause_text: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    risk_summary: str | None = None
    fact_value: str | None = None


class ClauseExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=1)
    content_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=25)


class ClauseExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clauses: list[ClauseMatch] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NarrativeFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class NarrativeFeatureExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=1)
    sections: list[RetrievalCandidate] = Field(default_factory=list)


class NarrativeFeatureExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: list[NarrativeFeature] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class EvidencePackagingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    used_by_agent: AgentTarget
    claim_it_supports: str = Field(min_length=1)
    retrieval_candidates: list[RetrievalCandidate] = Field(default_factory=list)
    sql_records: list[SqlMetricRecord] = Field(default_factory=list)


class EvidencePackagingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceReference] = Field(default_factory=list)


class AgentExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AgentRequest
    classification: QueryClassification
    route_plan: RoutePlan
    active_option_id: str | None = None
    comparison_options: list[ComparisonOption] = Field(default_factory=list)


class RetrievalAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    raw_candidates: list[RetrievalCandidate] = Field(default_factory=list)


class NarrativeAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    features: list[NarrativeFeature] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RoiAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    metrics: list[SqlMetricRecord] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RiskAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    clauses: list[ClauseMatch] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class CatalogAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    signals: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class HandoffOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: AgentTarget
    summary: str = Field(min_length=1)
    dependencies: list[AgentTarget] = Field(default_factory=list)


class OrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: QueryClassification
    route_plan: RoutePlan
    active_option_id: str | None = None
    comparison_option_ids: list[str] = Field(default_factory=list)
    retrieval_output: RetrievalAgentOutput | None = None
    narrative_output: NarrativeAgentOutput | None = None
    roi_output: RoiAgentOutput | None = None
    risk_output: RiskAgentOutput | None = None
    catalog_output: CatalogAgentOutput | None = None
    handoffs: list[HandoffOutput] = Field(default_factory=list)
    invoked_agents: list[AgentInvocation] = Field(default_factory=list)
    invoked_tools: list[ToolInvocation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

