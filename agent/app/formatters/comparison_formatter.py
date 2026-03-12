from __future__ import annotations

from typing import Any

from ..schemas.orchestration import OrchestrationResult


def _rank_recommendation(recommendation: str | None) -> int:
    ranks = {"GREENLIGHT": 3, "CONDITIONAL": 2, "PASS": 1}
    return ranks.get(recommendation or "", 0)


def _fallback_options() -> list[dict[str, Any]]:
    return [
        {
            "option_id": "option-a",
            "label": "Option A",
            "query_type": "original_eval",
            "recommendation": None,
            "estimated_roi": None,
            "catalog_fit_score": None,
            "risk_level": None,
        },
        {
            "option_id": "option-b",
            "label": "Option B",
            "query_type": "acquisition_eval",
            "recommendation": None,
            "estimated_roi": None,
            "catalog_fit_score": None,
            "risk_level": None,
        },
    ]


def _winner_id(options: list[dict[str, Any]]) -> str | None:
    if not options:
        return None
    ranked = sorted(
        options,
        key=lambda option: (
            -_rank_recommendation(option.get("recommendation")),
            -(option.get("estimated_roi") or float("-inf")),
            -(option.get("catalog_fit_score") or float("-inf")),
        ),
    )
    return ranked[0].get("option_id")


def format_comparison_scorecard(
    result: OrchestrationResult,
    comparison_state: dict[str, object] | None,
) -> dict[str, object]:
    options: list[dict[str, Any]] = []
    if isinstance(comparison_state, dict):
        for key in ("option_a", "option_b"):
            raw_option = comparison_state.get(key)
            if isinstance(raw_option, dict):
                options.append(dict(raw_option))

    if len(options) < 2:
        options = _fallback_options()

    current_option_id = result.active_option_id
    if current_option_id:
        for option in options:
            if option.get("option_id") != current_option_id:
                continue
            if result.recommendation_result is not None:
                option["recommendation"] = result.recommendation_result.outcome.value
            if result.roi_score is not None:
                option["estimated_roi"] = round(result.roi_score.estimated_roi, 4)
            if result.catalog_fit_score is not None:
                option["catalog_fit_score"] = round(result.catalog_fit_score.score, 2)
            if result.risk_score is not None:
                option["risk_level"] = result.risk_score.overall_severity.value

    axes = ["roi", "risk", "catalog_fit"]
    if isinstance(comparison_state, dict):
        raw_axes = comparison_state.get("comparison_axes")
        if isinstance(raw_axes, list) and raw_axes:
            axes = [str(axis) for axis in raw_axes]

    winner = _winner_id(options)
    winner_label = next(
        (option["label"] for option in options if option.get("option_id") == winner),
        "No clear winner",
    )
    summary = (
        f"{winner_label} currently leads based on recommendation strength, ROI, and risk profile."
        if winner is not None
        else "Comparison context is active, but no winning option is currently available."
    )
    return {
        "options": options,
        "winning_option_id": winner,
        "comparison_axes": axes,
        "summary": summary,
    }
