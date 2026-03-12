from __future__ import annotations

import hashlib
from collections.abc import Iterable

from app.schemas.ingestion import RetrievalMethod
from app.schemas.orchestration import EvidenceReference, OrchestrationResult


def _fingerprint(reference: EvidenceReference) -> str:
    key = "|".join(
        [
            reference.used_by_agent.value,
            reference.document_id or "",
            reference.section_id or "",
            reference.source_reference,
            reference.snippet,
            reference.claim_it_supports,
            reference.retrieval_method.value,
        ]
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _source_type(reference: EvidenceReference) -> str:
    if reference.retrieval_method in {RetrievalMethod.SQL, RetrievalMethod.DERIVED}:
        return "structured_metric"
    if reference.used_by_agent.value == "risk_contract_analysis":
        return "contract_fact"
    return "document_section"


def _iter_references(result: OrchestrationResult) -> Iterable[EvidenceReference]:
    outputs = [
        result.retrieval_output,
        result.narrative_output,
        result.roi_output,
        result.risk_output,
        result.catalog_output,
    ]
    for output in outputs:
        if output is None:
            continue
        yield from output.evidence


def format_evidence(result: OrchestrationResult) -> list[dict[str, object]]:
    deduped: dict[str, EvidenceReference] = {}
    for reference in _iter_references(result):
        evidence_id = _fingerprint(reference)
        current = deduped.get(evidence_id)
        if current is None or reference.confidence_score > current.confidence_score:
            deduped[evidence_id] = reference

    ordered = sorted(
        deduped.items(),
        key=lambda item: (-item[1].confidence_score, item[0]),
    )

    return [
        {
            "evidence_id": evidence_id,
            "source_type": _source_type(reference),
            "document_id": reference.document_id,
            "section_id": reference.section_id,
            "snippet": reference.snippet,
            "source_reference": reference.source_reference,
            "retrieval_method": reference.retrieval_method.value,
            "confidence_score": round(reference.confidence_score, 4),
            "used_by_agent": reference.used_by_agent.value,
            "claim_it_supports": reference.claim_it_supports,
        }
        for evidence_id, reference in ordered
    ]
