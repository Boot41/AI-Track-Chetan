from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.app.persistence.tables import document_facts, document_risks, document_sections, documents
from agent.app.schemas.ingestion import DocumentType
from agent.app.schemas.orchestration import ClauseExtractionRequest, ClauseExtractionResult, ClauseMatch


class ClauseExtractionTool:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run(self, request: ClauseExtractionRequest) -> ClauseExtractionResult:
        request = ClauseExtractionRequest.model_validate(request)
        tokens = [token for token in request.query_text.lower().split() if len(token) > 2]
        if not tokens:
            return ClauseExtractionResult(warnings=["No clause keywords were provided."])

        stmt: Select[tuple[object, ...]] = (
            select(
                documents.c.id.label("document_id"),
                document_sections.c.id.label("section_id"),
                document_sections.c.content.label("clause_text"),
                document_sections.c.source_reference.label("source_reference"),
                document_risks.c.summary.label("risk_summary"),
                document_facts.c.object_value.label("fact_value"),
            )
            .join(document_sections, document_sections.c.document_id == documents.c.id)
            .outerjoin(document_risks, document_risks.c.section_id == document_sections.c.id)
            .outerjoin(document_facts, document_facts.c.section_id == document_sections.c.id)
            .where(documents.c.document_type == DocumentType.CONTRACT.value)
            .where(or_(*[document_sections.c.content.ilike(f"%{token}%") for token in tokens]))
            .limit(request.limit)
        )
        if request.content_ids:
            stmt = stmt.where(documents.c.content_id.in_(request.content_ids))

        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).mappings().all()

        clauses = [
            ClauseMatch(
                document_id=str(row["document_id"]),
                section_id=str(row["section_id"]),
                clause_text=str(row["clause_text"]),
                source_reference=str(row["source_reference"]),
                risk_summary=str(row["risk_summary"]) if row["risk_summary"] is not None else None,
                fact_value=str(row["fact_value"]) if row["fact_value"] is not None else None,
            )
            for row in rows
        ]
        warnings = [] if clauses else ["No matching clauses were found."]
        return ClauseExtractionResult(clauses=clauses, warnings=warnings)
