from __future__ import annotations

from typing import Any

from ..schemas.eval_runner import RequiredEvidence


def calculate_recall_at_k(
    retrieved_evidence: list[dict[str, Any]],
    required_evidence: list[RequiredEvidence],
    k: int = 5,
) -> float:
    if not required_evidence:
        return 1.0

    retrieved_top_k = retrieved_evidence[:k]
    found_count = 0

    for required in required_evidence:
        found = False
        for retrieved in retrieved_top_k:
            # Check for source_reference match
            if (
                required.source_reference
                and retrieved.get("source_reference") == required.source_reference
            ):
                found = True
                break
            # Check for section_id match if source_reference not provided or if we want either
            if required.section_id and retrieved.get("section_id") == required.section_id:
                found = True
                break
        if found:
            found_count += 1

    return found_count / len(required_evidence)


def calculate_precision_at_k(
    retrieved_evidence: list[dict[str, Any]],
    relevant_labels: list[str] | None = None,
    k: int = 5,
) -> float | None:
    """
    Precision@k calculation. Requires relevant_labels (e.g., list of relevant section_ids).
    Returns None if labels are missing.
    """
    if relevant_labels is None:
        return None

    if not retrieved_evidence:
        return 0.0

    retrieved_top_k = retrieved_evidence[:k]
    relevant_count = 0

    for retrieved in retrieved_top_k:
        if retrieved.get("section_id") in relevant_labels:
            relevant_count += 1

    return relevant_count / len(retrieved_top_k)
