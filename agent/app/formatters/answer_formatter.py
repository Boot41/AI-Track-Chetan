from __future__ import annotations

from app.schemas.orchestration import OrchestrationResult, QueryType


def _join_refs(references: list[str]) -> str:
    unique = []
    seen = set()
    for reference in references:
        if reference in seen:
            continue
        seen.add(reference)
        unique.append(reference)
        if len(unique) == 3:
            break
    return "; ".join(unique)


def _narrative_followup_answer(result: OrchestrationResult) -> str:
    if result.narrative_output is None:
        return (
            "Narrative follow-up requested, but narrative signals were unavailable "
            "from the current retrieval set."
        )

    arcs = result.narrative_output.character_arcs
    if arcs:
        lead_arc = arcs[0]
        references = [item.source_reference for item in lead_arc.source_references]
        citation = _join_refs(references)
        answer = f"{lead_arc.character_name}: {lead_arc.arc_summary}"
        if citation:
            answer += f" Evidence: {citation}."
        return answer

    themes = ", ".join(result.narrative_output.themes[:3]) or "narrative themes"
    references = [
        item.source_reference for item in result.narrative_output.evidence[:3]
    ]
    citation = _join_refs(references)
    answer = (
        "Retrieved material supports a narrative-driven story shape focused on "
        f"{themes}."
    )
    if citation:
        answer += f" Evidence: {citation}."
    return answer


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
        if query_type == QueryType.FOLLOWUP_WHY_NARRATIVE:
            return _narrative_followup_answer(result)
        focus_area = scorecard.get("focus_area") or "requested area"
        return (
            f"This follow-up focuses on {focus_area} and explains "
            "the current recommendation context."
        )

    if query_type == QueryType.GENERAL_QUESTION:
        if result.retrieval_output:
            return f"General Question: {result.retrieval_output.summary}"
        return "Your question was processed, but no specific recommendation or retrieval context was found."

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
