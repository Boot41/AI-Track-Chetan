from __future__ import annotations

from agent.app.schemas.orchestration import (
    EvidencePackagingRequest,
    EvidencePackagingResult,
    EvidenceReference,
)
from agent.app.schemas.ingestion import RetrievalMethod


class EvidencePackagingTool:
    async def run(self, request: EvidencePackagingRequest) -> EvidencePackagingResult:
        request = EvidencePackagingRequest.model_validate(request)
        evidence = [
            EvidenceReference(
                document_id=candidate.document_id,
                section_id=candidate.section_id,
                snippet=candidate.snippet,
                source_reference=candidate.source_reference,
                retrieval_method=candidate.retrieval_method,
                confidence_score=candidate.confidence_score,
                used_by_agent=request.used_by_agent,
                claim_it_supports=request.claim_it_supports,
                metadata=candidate.claim_support_metadata,
            )
            for candidate in request.retrieval_candidates
        ]
        evidence.extend(
            EvidenceReference(
                document_id=None,
                section_id=None,
                snippet=f"{record.metric_key}: {record.value}",
                source_reference=record.source_reference,
                retrieval_method=RetrievalMethod.SQL,
                confidence_score=1.0,
                used_by_agent=request.used_by_agent,
                claim_it_supports=request.claim_it_supports,
                metadata={"source_table": record.source_table},
            )
            for record in request.sql_records
        )
        return EvidencePackagingResult(evidence=evidence)

