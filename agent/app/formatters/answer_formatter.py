from __future__ import annotations

from agent.app.schemas.orchestration import OrchestrationResult, QueryType


def _headline(result: OrchestrationResult, scorecard: dict[str, object]) -> str:
    query_type = result.classification.query_type
    recommendation = scorecard.get("recommendation")
    if query_type == QueryType.COMPARISON:
        comparison = scorecard.get("comparison")
        if isinstance(comparison, dict):
            winner = comparison.get("winning_option_id")
            summary = comparison.get("summary")
            if isinstance(winner, str) and winner:
                return f"{winner} is currently the stronger option. {summary}"
            if isinstance(summary, str):
                return summary
        return "Comparison context is active, but a definitive winner could not be determined."

    if query_type in {
        QueryType.FOLLOWUP_WHY_NARRATIVE,
        QueryType.FOLLOWUP_WHY_ROI,
        QueryType.FOLLOWUP_WHY_RISK,
        QueryType.FOLLOWUP_WHY_CATALOG,
    }:
        focus_area = scorecard.get("focus_area") or "requested area"
        return (
            f"This follow-up focuses on {focus_area} and explains "
            "the current recommendation context."
        )

    if isinstance(recommendation, str) and recommendation:
        return f"Recommendation: {recommendation}."
    return "A full recommendation could not be determined from the available signals."


def format_answer(
    result: OrchestrationResult,
    scorecard: dict[str, object],
    meta: dict[str, object],
) -> str:
    answer = _headline(result, scorecard)
    review_required = bool(meta.get("review_required"))
    confidence = meta.get("confidence")
    if review_required:
        answer += (
            " Evidence quality is limited, so manual review is required "
            "before a final decision."
        )
    elif isinstance(confidence, (float, int)) and float(confidence) < 0.65:
        answer += " Confidence is moderate because retrieval quality is uneven."
    return answer
