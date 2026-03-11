from __future__ import annotations

from collections import defaultdict


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"Expected numeric value, got {type(value)!r}")


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
    per_item_weight: dict[str, float] | None = None,
) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            weight = 1.0 if per_item_weight is None else per_item_weight.get(item_id, 1.0)
            scores[item_id] += weight / (k + rank)
    return dict(scores)


def rerank_candidates(
    candidates: list[dict[str, object]],
    *,
    limit: int,
) -> list[dict[str, object]]:
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            _as_float(candidate["fusion_score"]) * (0.5 + _as_float(candidate["structure_confidence"])),
            _as_float(candidate["method_score"]) * (0.5 + _as_float(candidate["structure_confidence"])),
            _as_float(candidate["structure_confidence"]),
        ),
        reverse=True,
    )
    return ranked[:limit]
