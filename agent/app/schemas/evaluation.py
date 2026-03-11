from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.app.schemas.ingestion import RetrievalMethod


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKER = "BLOCKER"


class RecommendationOutcome(StrEnum):
    GREENLIGHT = "GREENLIGHT"
    CONDITIONAL = "CONDITIONAL"
    PASS = "PASS"


class RetrievalFocus(StrEnum):
    CREATIVE = "creative"
    COMPARABLES = "comparables"
    CONTRACT = "contract"
    STRATEGIC = "strategic"


class RecommendationWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative_weight: float = 0.20
    roi_weight: float = 0.30
    risk_weight: float = 0.30
    catalog_fit_weight: float = 0.20

    @model_validator(mode="after")
    def validate_total(self) -> RecommendationWeights:
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


class RetrievalSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    retrieval_method: RetrievalMethod
    confidence_score: float = Field(ge=0.0, le=1.0)


class RetrievalEvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus: RetrievalFocus
    query_text: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class CharacterArcSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_name: str = Field(min_length=1)
    arc_summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class NarrativeRedFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag: str = Field(min_length=1)
    severity: RiskSeverity
    rationale: str = Field(min_length=1)
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class FranchiseAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class NarrativeScoreInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hook_strength: float = Field(ge=0.0, le=1.0)
    pacing_strength: float = Field(ge=0.0, le=1.0)
    character_strength: float = Field(ge=0.0, le=1.0)
    franchise_strength: float = Field(ge=0.0, le=1.0)
    red_flag_penalty: float = Field(ge=0.0, le=1.0)


class ComparableTitleEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class CompletionRateInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_completion_rate: float = Field(ge=0.0, le=1.0)
    comparable_completion_rate: float = Field(ge=0.0, le=1.0)
    hook_strength: float = Field(ge=0.0, le=1.0)
    bingeability: float = Field(ge=0.0, le=1.0)
    pacing_penalty: float = Field(ge=0.0, le=1.0)
    narrative_clarity_penalty: float = Field(ge=0.0, le=1.0)


class RetentionLiftInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_retention_lift: float
    audience_alignment: float = Field(ge=0.0, le=1.0)
    churn_reduction_signal: float = Field(ge=0.0, le=1.0)
    franchise_uplift: float = Field(ge=0.0, le=1.0)
    regional_demand_signal: float = Field(ge=0.0, le=1.0)


class RoiInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cost: float = Field(ge=0.0)
    projected_viewers: float = Field(ge=0.0)
    projected_revenue: float = Field(ge=0.0)
    retention_value: float = Field(ge=0.0)
    franchise_value: float = Field(ge=0.0)


class CostPerViewInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cost: float = Field(ge=0.0)
    projected_viewers: float = Field(gt=0.0)


class RiskFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_type: str = Field(min_length=1)
    severity_input: RiskSeverity
    rationale: str = Field(min_length=1)
    remediation_hint: str | None = None
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class CatalogFitSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str = Field(min_length=1)
    strength: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
    source_references: list[RetrievalSourceReference] = Field(default_factory=list)


class CatalogFitInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    underserved_segments: list[CatalogFitSignal] = Field(default_factory=list)
    churn_demographics: list[CatalogFitSignal] = Field(default_factory=list)
    genre_gaps: list[CatalogFitSignal] = Field(default_factory=list)
    regional_demand: list[CatalogFitSignal] = Field(default_factory=list)
    competitor_overlap: list[CatalogFitSignal] = Field(default_factory=list)
    strategic_timing: list[CatalogFitSignal] = Field(default_factory=list)
    localization_implications: list[CatalogFitSignal] = Field(default_factory=list)


class CompletionRateScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projected_completion_rate: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class RoiScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimated_roi: float
    cost_per_view: float = Field(ge=0.0)
    retention_lift: float
    rationale: str = Field(min_length=1)


class RiskScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_severity: RiskSeverity
    safety_score: float = Field(ge=0.0, le=100.0)
    rationale: str = Field(min_length=1)


class CatalogFitScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=100.0)
    rationale: str = Field(min_length=1)


class RecommendationContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str = Field(min_length=1)
    raw_score: float = Field(ge=0.0, le=100.0)
    weighted_score: float = Field(ge=0.0, le=100.0)
    rationale: str = Field(min_length=1)


class RecommendationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: RecommendationOutcome
    weighted_score: float = Field(ge=0.0, le=100.0)
    override_applied: str | None = None
    contributions: list[RecommendationContribution] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
