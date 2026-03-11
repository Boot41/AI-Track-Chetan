from __future__ import annotations

from agent.app.formatters import format_public_response
from agent.app.formatters.evidence_formatter import format_evidence
from agent.app.formatters.scorecard_formatter import format_scorecard
from agent.app.formatters.uncertainty_formatter import format_meta
from agent.app.schemas.evaluation import (
    CatalogFitScore,
    CompletionRateScore,
    RecommendationContribution,
    RecommendationOutcome,
    RecommendationResult,
    RiskScore,
    RiskSeverity,
    RoiScore,
)
from agent.app.schemas.ingestion import DocumentType, RetrievalMethod
from agent.app.schemas.orchestration import (
    AgentTarget,
    EvidenceReference,
    OrchestrationResult,
    QueryClassification,
    QueryType,
    RetrievalAgentOutput,
    RoutePlan,
)
from agent.app.schemas.retrieval import RetrievalCandidate


def _base_result(query_type: QueryType = QueryType.ORIGINAL_EVAL) -> OrchestrationResult:
    return OrchestrationResult(
        classification=QueryClassification(
            query_type=query_type,
            target_agents=[AgentTarget.DOCUMENT_RETRIEVAL],
            reuse_cached_outputs=False,
            requires_recomputation=True,
        ),
        route_plan=RoutePlan(
            query_type=query_type,
            agent_sequence=[AgentTarget.DOCUMENT_RETRIEVAL],
        ),
    )


def test_evidence_formatter_keeps_traceability_fields() -> None:
    result = _base_result()
    result.retrieval_output = RetrievalAgentOutput(
        summary="retrieval",
        evidence=[
            EvidenceReference(
                document_id="doc-1",
                section_id="sec-1",
                snippet="Key clause text.",
                source_reference="contract.md#sec-1",
                retrieval_method=RetrievalMethod.HYBRID,
                confidence_score=0.72,
                used_by_agent=AgentTarget.RISK_CONTRACT_ANALYSIS,
                claim_it_supports="rights restriction risk",
            )
        ],
        raw_candidates=[],
    )
    evidence = format_evidence(result)
    assert len(evidence) == 1
    assert evidence[0]["document_id"] == "doc-1"
    assert evidence[0]["section_id"] == "sec-1"
    assert evidence[0]["source_reference"] == "contract.md#sec-1"
    assert evidence[0]["retrieval_method"] == "hybrid"
    assert evidence[0]["confidence_score"] == 0.72
    assert evidence[0]["used_by_agent"] == "risk_contract_analysis"
    assert evidence[0]["claim_it_supports"] == "rights restriction risk"


def test_uncertainty_formatter_sets_review_required_for_low_confidence() -> None:
    result = _base_result(QueryType.GENERAL_QUESTION)
    result.retrieval_output = RetrievalAgentOutput(
        summary="retrieval",
        evidence=[],
        raw_candidates=[
            RetrievalCandidate(
                document_id="doc-1",
                section_id="sec-1",
                snippet="low-structure text",
                source_reference="doc.md#sec-1",
                retrieval_method=RetrievalMethod.FTS,
                confidence_score=0.31,
                document_type=DocumentType.REPORT,
                claim_support_metadata={"structure_confidence": 0.2},
            )
        ],
    )
    meta = format_meta(result, [])
    assert meta["review_required"] is True
    assert isinstance(meta["warnings"], list)
    assert any("low-structure" in warning for warning in meta["warnings"])


def test_scorecard_formatter_supports_followup_partial_updates() -> None:
    result = _base_result(QueryType.FOLLOWUP_WHY_ROI)
    result.roi_score = RoiScore(
        estimated_roi=1.2,
        cost_per_view=3.1,
        retention_lift=0.04,
        rationale="roi rationale",
    )
    previous = {
        "scorecard_type": "evaluation",
        "query_type": "original_eval",
        "title": "Previous",
        "recommendation": "CONDITIONAL",
        "narrative_score": 65.0,
        "projected_completion_rate": 0.61,
        "estimated_roi": 1.1,
        "catalog_fit_score": 70.0,
        "risk_level": "MEDIUM",
        "risk_flags": [],
        "comparison": None,
        "focus_area": None,
    }
    scorecard = format_scorecard(result, previous, comparison_state=None)
    assert scorecard["scorecard_type"] == "followup"
    assert scorecard["query_type"] == "followup_why_roi"
    assert scorecard["focus_area"] == "roi"
    assert scorecard["recommendation"] == "CONDITIONAL"
    assert scorecard["estimated_roi"] == 1.2


def test_response_formatter_comparison_keeps_stable_envelope() -> None:
    result = _base_result(QueryType.COMPARISON)
    result.recommendation_result = RecommendationResult(
        outcome=RecommendationOutcome.GREENLIGHT,
        weighted_score=74.0,
        override_applied=None,
        contributions=[
            RecommendationContribution(
                component="roi",
                raw_score=74.0,
                weighted_score=22.2,
                rationale="roi",
            )
        ],
        rationale="recommendation",
    )
    result.roi_score = RoiScore(
        estimated_roi=1.32,
        cost_per_view=2.8,
        retention_lift=0.05,
        rationale="roi",
    )
    result.catalog_fit_score = CatalogFitScore(score=77.0, rationale="fit")
    result.risk_score = RiskScore(
        overall_severity=RiskSeverity.LOW,
        safety_score=86.0,
        rationale="risk",
    )
    result.completion_score = CompletionRateScore(
        projected_completion_rate=0.64,
        rationale="completion",
    )
    payload = format_public_response(
        result,
        previous_scorecard=None,
        comparison_state={
            "option_a": {
                "option_id": "option-a",
                "label": "Option A",
                "query_type": "original_eval",
            },
            "option_b": {
                "option_id": "option-b",
                "label": "Option B",
                "query_type": "acquisition_eval",
            },
            "comparison_axes": ["roi", "risk", "catalog_fit"],
            "active_option": "option-a",
        },
    )
    assert set(payload) == {"answer", "scorecard", "evidence", "meta"}
    assert payload["scorecard"]["scorecard_type"] == "comparison"
    assert payload["scorecard"]["comparison"] is not None
    assert set(payload["meta"]) == {"warnings", "confidence", "review_required"}
