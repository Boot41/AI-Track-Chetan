from __future__ import annotations

from agent.app.formatters.comparison_formatter import format_comparison_scorecard
from agent.app.schemas.orchestration import OrchestrationResult, QueryType

_FOLLOWUP_FOCUS: dict[QueryType, str] = {
    QueryType.FOLLOWUP_WHY_NARRATIVE: "narrative",
    QueryType.FOLLOWUP_WHY_ROI: "roi",
    QueryType.FOLLOWUP_WHY_RISK: "risk",
    QueryType.FOLLOWUP_WHY_CATALOG: "catalog_fit",
}


def _empty_scorecard(query_type: QueryType) -> dict[str, object]:
    if query_type == QueryType.COMPARISON:
        scorecard_type = "comparison"
    elif query_type in _FOLLOWUP_FOCUS:
        scorecard_type = "followup"
    else:
        scorecard_type = "evaluation"
    return {
        "scorecard_type": scorecard_type,
        "query_type": query_type.value,
        "title": "StreamLogic Evaluation",
        "recommendation": None,
        "narrative_score": None,
        "projected_completion_rate": None,
        "estimated_roi": None,
        "catalog_fit_score": None,
        "risk_level": None,
        "risk_flags": [],
        "comparison": None,
        "focus_area": None,
    }


def _title_for(query_type: QueryType) -> str:
    if query_type == QueryType.COMPARISON:
        return "Content Opportunity Comparison"
    if query_type in _FOLLOWUP_FOCUS:
        return "Follow-Up Analysis"
    if query_type == QueryType.ACQUISITION_EVAL:
        return "Catalog Acquisition Evaluation"
    return "Original Content Evaluation"


def _risk_flags(result: OrchestrationResult) -> list[dict[str, object]]:
    if result.risk_output is None:
        return []
    return [
        {
            "code": finding.risk_type,
            "severity": finding.severity_input.value,
            "summary": finding.rationale,
        }
        for finding in result.risk_output.findings
    ]


def _merge_with_previous(
    previous_scorecard: dict[str, object] | None,
    query_type: QueryType,
) -> dict[str, object]:
    base = _empty_scorecard(query_type)
    if not isinstance(previous_scorecard, dict):
        return base
    for key in base:
        if key in previous_scorecard:
            base[key] = previous_scorecard[key]
    return base


def format_scorecard(
    result: OrchestrationResult,
    previous_scorecard: dict[str, object] | None,
    comparison_state: dict[str, object] | None,
) -> dict[str, object]:
    query_type = result.classification.query_type
    scorecard = _merge_with_previous(previous_scorecard, query_type)
    scorecard["query_type"] = query_type.value
    scorecard["title"] = _title_for(query_type)

    if query_type == QueryType.COMPARISON:
        scorecard["scorecard_type"] = "comparison"
        scorecard["comparison"] = format_comparison_scorecard(result, comparison_state)
        scorecard["focus_area"] = None
    elif query_type in _FOLLOWUP_FOCUS:
        scorecard["scorecard_type"] = "followup"
        scorecard["comparison"] = None
        scorecard["focus_area"] = _FOLLOWUP_FOCUS[query_type]
    else:
        scorecard["scorecard_type"] = "evaluation"
        scorecard["comparison"] = None
        scorecard["focus_area"] = None

    if result.recommendation_result is not None:
        scorecard["recommendation"] = result.recommendation_result.outcome.value
    if result.completion_score is not None:
        scorecard["projected_completion_rate"] = round(
            result.completion_score.projected_completion_rate, 4
        )
    if result.roi_score is not None:
        scorecard["estimated_roi"] = round(result.roi_score.estimated_roi, 4)
    if result.catalog_fit_score is not None:
        scorecard["catalog_fit_score"] = round(result.catalog_fit_score.score, 2)
    if result.risk_score is not None:
        scorecard["risk_level"] = result.risk_score.overall_severity.value
    if result.risk_output is not None:
        scorecard["risk_flags"] = _risk_flags(result)

    if result.recommendation_result is not None:
        for contribution in result.recommendation_result.contributions:
            if contribution.component == "narrative":
                scorecard["narrative_score"] = round(contribution.raw_score, 2)
                break

    return scorecard
