from __future__ import annotations

from agent.app.formatters.answer_formatter import format_answer
from agent.app.formatters.evidence_formatter import format_evidence
from agent.app.formatters.scorecard_formatter import format_scorecard
from agent.app.formatters.uncertainty_formatter import format_meta
from agent.app.schemas.orchestration import OrchestrationResult


def format_public_response(
    result: OrchestrationResult,
    previous_scorecard: dict[str, object] | None = None,
    comparison_state: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence = format_evidence(result)
    meta = format_meta(result, evidence)
    scorecard = format_scorecard(result, previous_scorecard, comparison_state)
    answer = format_answer(result, scorecard, meta)
    return {
        "answer": answer,
        "scorecard": scorecard,
        "evidence": evidence,
        "meta": meta,
    }
