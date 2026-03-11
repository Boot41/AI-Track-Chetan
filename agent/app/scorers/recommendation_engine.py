from __future__ import annotations

from agent.app.schemas.evaluation import (
    CatalogFitScore,
    NarrativeScoreInputs,
    RecommendationConfig,
    RecommendationContribution,
    RecommendationOutcome,
    RecommendationResult,
    RiskScore,
    RiskSeverity,
    RoiScore,
)


class RecommendationEngine:
    def __init__(self, config: RecommendationConfig | None = None) -> None:
        self._config = config or RecommendationConfig()

    @property
    def config(self) -> RecommendationConfig:
        return self._config

    def score_narrative(self, inputs: NarrativeScoreInputs) -> float:
        inputs = NarrativeScoreInputs.model_validate(inputs)
        score = (
            inputs.hook_strength * 0.30
            + inputs.pacing_strength * 0.25
            + inputs.character_strength * 0.25
            + inputs.franchise_strength * 0.20
            - inputs.red_flag_penalty * 0.25
        ) * 100
        return round(max(0.0, min(100.0, score)), 2)

    def score_roi(self, score: RoiScore) -> float:
        score = RoiScore.model_validate(score)
        roi_component = max(0.0, min(100.0, (score.estimated_roi + 0.5) * 50))
        cpv_component = max(0.0, min(100.0, 100.0 - score.cost_per_view * 12))
        retention_component = max(0.0, min(100.0, score.retention_lift * 1200))
        return round(roi_component * 0.55 + cpv_component * 0.20 + retention_component * 0.25, 2)

    def recommend(
        self,
        narrative_inputs: NarrativeScoreInputs,
        roi_score: RoiScore,
        risk_score: RiskScore,
        catalog_fit_score: CatalogFitScore,
    ) -> RecommendationResult:
        narrative_score = self.score_narrative(narrative_inputs)
        roi_component = self.score_roi(roi_score)
        risk_component = risk_score.safety_score
        catalog_component = catalog_fit_score.score

        weights = self._config.weights
        contributions = [
            RecommendationContribution(
                component="narrative",
                raw_score=narrative_score,
                weighted_score=round(narrative_score * weights.narrative_weight, 2),
                rationale="Narrative strength is derived from deterministic story-quality inputs.",
            ),
            RecommendationContribution(
                component="roi",
                raw_score=roi_component,
                weighted_score=round(roi_component * weights.roi_weight, 2),
                rationale="ROI combines completion-adjusted economics, retention lift, and unit cost.",
            ),
            RecommendationContribution(
                component="risk",
                raw_score=risk_component,
                weighted_score=round(risk_component * weights.risk_weight, 2),
                rationale="Risk uses the conservative safety score from surfaced legal and regulatory findings.",
            ),
            RecommendationContribution(
                component="catalog_fit",
                raw_score=catalog_component,
                weighted_score=round(catalog_component * weights.catalog_fit_weight, 2),
                rationale="Catalog fit reflects demand gaps, churn pressure, timing, and overlap.",
            ),
        ]
        weighted_score = round(sum(item.weighted_score for item in contributions), 2)
        outcome = self._base_outcome(weighted_score)
        override_applied: str | None = None

        if risk_score.overall_severity == RiskSeverity.BLOCKER:
            outcome = self._config.overrides.blocker_risk_forces
            override_applied = "blocker_risk_forced_pass"
        elif (
            risk_score.overall_severity == RiskSeverity.HIGH
            and outcome == RecommendationOutcome.GREENLIGHT
        ):
            outcome = self._config.overrides.high_risk_caps_at
            override_applied = "high_risk_capped_recommendation"

        return RecommendationResult(
            outcome=outcome,
            weighted_score=weighted_score,
            override_applied=override_applied,
            contributions=contributions,
            rationale="Recommendation computed from configuration-driven weights and explicit risk overrides.",
        )

    def _base_outcome(self, weighted_score: float) -> RecommendationOutcome:
        if weighted_score >= 70.0:
            return RecommendationOutcome.GREENLIGHT
        if weighted_score >= 45.0:
            return RecommendationOutcome.CONDITIONAL
        return RecommendationOutcome.PASS
