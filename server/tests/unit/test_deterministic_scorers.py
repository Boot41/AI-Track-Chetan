from __future__ import annotations

from agent.app.schemas.evaluation import (
    CatalogFitInputs,
    CatalogFitSignal,
    CompletionRateInputs,
    CompletionRateScore,
    CostPerViewInputs,
    NarrativeScoreInputs,
    RetentionLiftInputs,
    RiskFinding,
    RiskSeverity,
    RoiInputs,
)
from agent.app.scorers import (
    CatalogFitScorer,
    CompletionRateScorer,
    RecommendationEngine,
    RiskSeverityScorer,
    RoiScorer,
)


def test_completion_rate_scorer_returns_stable_projection() -> None:
    result = CompletionRateScorer().score(
        CompletionRateInputs(
            baseline_completion_rate=0.62,
            comparable_completion_rate=0.69,
            hook_strength=0.86,
            bingeability=0.8,
            pacing_penalty=0.12,
            narrative_clarity_penalty=0.08,
        )
    )
    assert 0.05 <= result.projected_completion_rate <= 0.95
    assert result.projected_completion_rate == 0.6693


def test_roi_scorer_combines_completion_retention_and_unit_cost() -> None:
    completion_score = CompletionRateScore(
        projected_completion_rate=0.7,
        rationale="test",
    )
    result = RoiScorer().score(
        RoiInputs(
            total_cost=50000000.0,
            projected_viewers=20000000.0,
            projected_revenue=120000000.0,
            retention_value=15000000.0,
            franchise_value=10000000.0,
        ),
        RetentionLiftInputs(
            baseline_retention_lift=0.04,
            audience_alignment=0.8,
            churn_reduction_signal=0.75,
            franchise_uplift=0.6,
            regional_demand_signal=0.7,
        ),
        CostPerViewInputs(total_cost=50000000.0, projected_viewers=20000000.0),
        completion_score,
    )
    assert result.estimated_roi == 1.18
    assert result.cost_per_view == 2.5
    assert result.retention_lift == 0.0691


def test_catalog_fit_scorer_handles_positive_and_overlap_signals() -> None:
    result = CatalogFitScorer().score(
        CatalogFitInputs(
            underserved_segments=[
                CatalogFitSignal(
                    signal="underserved",
                    strength=0.8,
                    rationale="test",
                    source_references=[],
                )
            ],
            churn_demographics=[
                CatalogFitSignal(
                    signal="churn",
                    strength=0.7,
                    rationale="test",
                    source_references=[],
                )
            ],
            genre_gaps=[],
            regional_demand=[],
            competitor_overlap=[
                CatalogFitSignal(
                    signal="overlap",
                    strength=0.4,
                    rationale="test",
                    source_references=[],
                )
            ],
            strategic_timing=[],
            localization_implications=[],
        )
    )
    assert result.score == 19.0


def test_risk_severity_scorer_defaults_to_low_when_findings_are_absent() -> None:
    result = RiskSeverityScorer().score([])
    assert result.overall_severity == RiskSeverity.LOW
    assert result.safety_score == 92.0


def test_risk_severity_scorer_uses_worst_case_severity() -> None:
    result = RiskSeverityScorer().score(
        [
            RiskFinding(
                risk_type="review",
                severity_input=RiskSeverity.MEDIUM,
                rationale="test",
                source_references=[],
            ),
            RiskFinding(
                risk_type="matching_rights",
                severity_input=RiskSeverity.BLOCKER,
                rationale="test",
                source_references=[],
            ),
        ]
    )
    assert result.overall_severity == RiskSeverity.BLOCKER
    assert result.safety_score == 5.0


def test_recommendation_engine_applies_weights_and_high_risk_cap() -> None:
    engine = RecommendationEngine()
    recommendation = engine.recommend(
        NarrativeScoreInputs(
            hook_strength=1.0,
            pacing_strength=1.0,
            character_strength=1.0,
            franchise_strength=1.0,
            red_flag_penalty=0.0,
        ),
        roi_score=RoiScorer().score(
            RoiInputs(
                total_cost=30000000.0,
                projected_viewers=26000000.0,
                projected_revenue=180000000.0,
                retention_value=18000000.0,
                franchise_value=14000000.0,
            ),
            RetentionLiftInputs(
                baseline_retention_lift=0.04,
                audience_alignment=0.9,
                churn_reduction_signal=0.9,
                franchise_uplift=0.8,
                regional_demand_signal=0.85,
            ),
            CostPerViewInputs(total_cost=30000000.0, projected_viewers=26000000.0),
            CompletionRateScore(projected_completion_rate=0.88, rationale="test"),
        ),
        risk_score=RiskSeverityScorer().score(
            [
                RiskFinding(
                    risk_type="overlap",
                    severity_input=RiskSeverity.HIGH,
                    rationale="test",
                    source_references=[],
                )
            ]
        ),
        catalog_fit_score=CatalogFitScorer().score(
            CatalogFitInputs(
                underserved_segments=[
                    CatalogFitSignal(
                        signal="gap",
                        strength=1.0,
                        rationale="test",
                        source_references=[],
                    )
                ],
                churn_demographics=[
                    CatalogFitSignal(
                        signal="churn",
                        strength=1.0,
                        rationale="test",
                        source_references=[],
                    )
                ],
                genre_gaps=[
                    CatalogFitSignal(
                        signal="genre",
                        strength=1.0,
                        rationale="test",
                        source_references=[],
                    )
                ],
                regional_demand=[
                    CatalogFitSignal(
                        signal="regional",
                        strength=1.0,
                        rationale="test",
                        source_references=[],
                    )
                ],
                competitor_overlap=[],
                strategic_timing=[
                    CatalogFitSignal(
                        signal="timing",
                        strength=1.0,
                        rationale="test",
                        source_references=[],
                    )
                ],
                localization_implications=[
                    CatalogFitSignal(
                        signal="localization",
                        strength=1.0,
                        rationale="test",
                        source_references=[],
                    )
                ],
            )
        ),
    )
    assert recommendation.outcome.value == "CONDITIONAL"
    assert recommendation.override_applied == "high_risk_capped_recommendation"


def test_recommendation_engine_blocker_risk_forces_pass() -> None:
    engine = RecommendationEngine()
    recommendation = engine.recommend(
        NarrativeScoreInputs(
            hook_strength=0.95,
            pacing_strength=0.9,
            character_strength=0.85,
            franchise_strength=0.9,
            red_flag_penalty=0.0,
        ),
        roi_score=RoiScorer().score(
            RoiInputs(
                total_cost=35000000.0,
                projected_viewers=22000000.0,
                projected_revenue=150000000.0,
                retention_value=14000000.0,
                franchise_value=11000000.0,
            ),
            RetentionLiftInputs(
                baseline_retention_lift=0.04,
                audience_alignment=0.85,
                churn_reduction_signal=0.8,
                franchise_uplift=0.8,
                regional_demand_signal=0.75,
            ),
            CostPerViewInputs(total_cost=35000000.0, projected_viewers=22000000.0),
            CompletionRateScore(projected_completion_rate=0.78, rationale="test"),
        ),
        risk_score=RiskSeverityScorer().score(
            [
                RiskFinding(
                    risk_type="matching_rights",
                    severity_input=RiskSeverity.BLOCKER,
                    rationale="test",
                    source_references=[],
                )
            ]
        ),
        catalog_fit_score=CatalogFitScorer().score(
            CatalogFitInputs(
                underserved_segments=[
                    CatalogFitSignal(
                        signal="gap",
                        strength=0.95,
                        rationale="test",
                        source_references=[],
                    )
                ],
                churn_demographics=[],
                genre_gaps=[],
                regional_demand=[],
                competitor_overlap=[],
                strategic_timing=[],
                localization_implications=[],
            )
        ),
    )
    assert recommendation.outcome.value == "PASS"
    assert recommendation.override_applied == "blocker_risk_forced_pass"
