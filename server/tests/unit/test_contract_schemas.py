from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agent.routing_spec import ROUTING_SPEC
from app.schemas.contracts import (
    AgentRequestEnvelope,
    AgentTarget,
    ComparisonAxis,
    ComparisonOption,
    ComparisonScorecard,
    DocumentFactContract,
    EvaluationScorecard,
    MetaContract,
    QueryClassification,
    QueryType,
    RecommendationConfig,
    RecommendationOutcome,
    RecommendationWeights,
    RiskFlag,
    RiskSeverity,
    ScorecardType,
    SessionAgentOutput,
    SessionState,
    TrustedRequestContext,
)


def test_public_meta_contract_stays_minimal() -> None:
    meta = MetaContract(warnings=["low recall"], confidence=0.5, review_required=True)
    assert meta.model_dump() == {
        "warnings": ["low recall"],
        "confidence": 0.5,
        "review_required": True,
    }


def test_query_classification_schema_accepts_phase0_values() -> None:
    classification = QueryClassification(
        query_type=QueryType.SCENARIO_CHANGE_LOCALIZATION,
        target_agents=[
            AgentTarget.ROI_PREDICTION,
            AgentTarget.CATALOG_FIT,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        reuse_cached_outputs=True,
        requires_recomputation=True,
    )
    assert classification.query_type == QueryType.SCENARIO_CHANGE_LOCALIZATION


def test_routing_spec_covers_every_supported_query_type() -> None:
    assert set(ROUTING_SPEC) == set(QueryType)
    assert ROUTING_SPEC[QueryType.FOLLOWUP_WHY_RISK].target_agents == [
        AgentTarget.RISK_CONTRACT_ANALYSIS
    ]
    assert ROUTING_SPEC[QueryType.SCENARIO_CHANGE_BUDGET].requires_recomputation is True


def test_recommendation_config_defaults_are_locked() -> None:
    config = RecommendationConfig()
    assert config.weights.model_dump() == {
        "narrative_weight": 0.2,
        "roi_weight": 0.3,
        "risk_weight": 0.3,
        "catalog_fit_weight": 0.2,
    }
    assert config.overrides.blocker_risk_forces == RecommendationOutcome.PASS
    assert config.overrides.high_risk_caps_at == RecommendationOutcome.CONDITIONAL


def test_recommendation_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        RecommendationWeights(
            narrative_weight=0.2,
            roi_weight=0.3,
            risk_weight=0.3,
            catalog_fit_weight=0.3,
        )


def test_comparison_state_requires_valid_active_option() -> None:
    option_a = ComparisonOption(
        option_id="option-a",
        label="Option A",
        query_type=QueryType.ORIGINAL_EVAL,
    )
    option_b = ComparisonOption(
        option_id="option-b",
        label="Option B",
        query_type=QueryType.ACQUISITION_EVAL,
    )
    comparison = ComparisonScorecard(
        options=[option_a, option_b],
        winning_option_id="option-a",
        comparison_axes=[ComparisonAxis.ROI, ComparisonAxis.RISK],
        summary="Option A has higher upside.",
    )

    state = SessionState(
        query_type=QueryType.COMPARISON,
        comparison_state={
            "option_a": option_a.model_dump(),
            "option_b": option_b.model_dump(),
            "comparison_scorecard": comparison.model_dump(),
            "comparison_axes": ["roi", "risk"],
            "active_option": "option-b",
        },
        active_option="option-b",
    )

    assert state.comparison_state is not None
    assert state.comparison_state.active_option == "option-b"


def test_comparison_scorecard_winner_must_match_listed_option() -> None:
    option_a = ComparisonOption(
        option_id="option-a",
        label="Option A",
        query_type=QueryType.ORIGINAL_EVAL,
    )
    option_b = ComparisonOption(
        option_id="option-b",
        label="Option B",
        query_type=QueryType.ACQUISITION_EVAL,
    )

    with pytest.raises(ValidationError):
        ComparisonScorecard(
            options=[option_a, option_b],
            winning_option_id="option-c",
            comparison_axes=[ComparisonAxis.ROI],
            summary="Invalid winner.",
        )


def test_session_state_requires_consistent_active_option() -> None:
    option_a = ComparisonOption(
        option_id="option-a",
        label="Option A",
        query_type=QueryType.ORIGINAL_EVAL,
    )
    option_b = ComparisonOption(
        option_id="option-b",
        label="Option B",
        query_type=QueryType.ACQUISITION_EVAL,
    )

    with pytest.raises(ValidationError):
        SessionState(
            query_type=QueryType.COMPARISON,
            comparison_state={
                "option_a": option_a.model_dump(),
                "option_b": option_b.model_dump(),
                "comparison_axes": ["roi"],
                "active_option": "option-a",
            },
            active_option="option-b",
        )


def test_followup_scorecard_requires_focus_area() -> None:
    with pytest.raises(ValidationError):
        EvaluationScorecard(
            scorecard_type=ScorecardType.FOLLOWUP,
            query_type=QueryType.FOLLOWUP_WHY_ROI,
            title="ROI follow-up",
            recommendation=RecommendationOutcome.CONDITIONAL,
        )


def test_agent_request_envelope_supports_cached_session_state() -> None:
    request = AgentRequestEnvelope(
        message="Why is the ROI low?",
        context=TrustedRequestContext(user_id=1, session_id="session-1"),
        session_state=SessionState(
            query_type=QueryType.FOLLOWUP_WHY_ROI,
            roi_output=SessionAgentOutput(
                summary="ROI is sensitive to budget pressure.",
                confidence=0.81,
                generated_at=datetime.now(UTC),
            ),
        ),
    )
    assert request.context.user_id == 1
    assert request.session_state is not None


def test_document_fact_contract_is_contract_only_and_atomic() -> None:
    fact = DocumentFactContract(
        fact_id="fact-1",
        document_id="doc-1",
        section_id="section-9",
        subject="license",
        predicate="territory_scope",
        object_value="India and Indonesia",
        qualifier="approval required outside territory",
        source_text="Rights are limited to India and Indonesia.",
        confidence=0.97,
        extracted_by="contract_clause_extractor",
    )
    assert fact.predicate == "territory_scope"
    assert fact.extracted_by == "contract_clause_extractor"


def test_risk_flag_schema_allows_locked_severities() -> None:
    risk = RiskFlag(code="territory_restriction", severity=RiskSeverity.HIGH, summary="Limited SEA")
    assert risk.severity == RiskSeverity.HIGH
