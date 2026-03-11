from __future__ import annotations

from typing import Any

from agent.app.schemas.orchestration import OrchestrationResult

LOW_CONFIDENCE_THRESHOLD = 0.55
REVIEW_REQUIRED_THRESHOLD = 0.45
LOW_STRUCTURE_CONFIDENCE = 0.5


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _evidence_confidence(evidence: list[dict[str, object]]) -> tuple[float, int]:
    confidences: list[float] = []
    for item in evidence:
        score: Any = item.get("confidence_score")
        if isinstance(score, (float, int)):
            confidences.append(float(score))
    if not confidences:
        return (0.0, 0)
    return (sum(confidences) / len(confidences), len(confidences))


def _structure_confidence_warnings(result: OrchestrationResult) -> list[str]:
    warnings: list[str] = []
    retrieval_output = result.retrieval_output
    if retrieval_output is None:
        return warnings
    low_structure_count = 0
    for candidate in retrieval_output.raw_candidates:
        structure_confidence = candidate.claim_support_metadata.get("structure_confidence")
        if (
            isinstance(structure_confidence, (int, float))
            and structure_confidence < LOW_STRUCTURE_CONFIDENCE
        ):
            low_structure_count += 1
    if low_structure_count > 0:
        warnings.append(
            "Some retrieved sections came from low-structure parsing and "
            "should be reviewed manually."
        )
    return warnings


def _orchestration_confidence(result: OrchestrationResult) -> float:
    components: list[float] = []
    if result.recommendation_result is not None:
        components.append(_bounded(result.recommendation_result.weighted_score / 100.0))
    if result.risk_score is not None:
        components.append(_bounded(result.risk_score.safety_score / 100.0))
    if result.catalog_fit_score is not None:
        components.append(_bounded(result.catalog_fit_score.score / 100.0))
    if not components:
        return 0.0
    return sum(components) / len(components)


def format_meta(
    result: OrchestrationResult,
    evidence: list[dict[str, object]],
) -> dict[str, object]:
    warnings = list(dict.fromkeys([*result.warnings, *_structure_confidence_warnings(result)]))
    evidence_avg_confidence, evidence_count = _evidence_confidence(evidence)
    orchestration_confidence = _orchestration_confidence(result)
    retrieval_grounded_count = (
        len(result.retrieval_output.raw_candidates)
        if result.retrieval_output is not None
        else 0
    )

    if evidence_count == 0 or retrieval_grounded_count == 0:
        warnings.append("No supporting evidence was retrieved for this response.")
    elif evidence_avg_confidence < LOW_CONFIDENCE_THRESHOLD:
        warnings.append("Supporting evidence confidence is low.")

    confidence = _bounded(
        0.7 * evidence_avg_confidence + 0.3 * orchestration_confidence
        if evidence_count > 0
        else orchestration_confidence * 0.5
    )
    review_required = (
        evidence_count == 0
        or retrieval_grounded_count == 0
        or confidence < REVIEW_REQUIRED_THRESHOLD
        or any("low-structure" in warning for warning in warnings)
    )
    return {
        "warnings": warnings,
        "confidence": round(confidence, 4),
        "review_required": review_required,
    }
