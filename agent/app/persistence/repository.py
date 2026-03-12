from __future__ import annotations

from collections.abc import Sequence
import json

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.tables import document_facts, document_risks, document_sections, documents
from app.schemas.ingestion import DocumentMetadata, SectionRecord


class DocumentRepository:
    async def _embedding_column_is_vector(self, session: AsyncSession) -> bool:
        result = await session.execute(
            text(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_name = 'document_sections' AND column_name = 'embedding'
                """
            )
        )
        udt_name = result.scalar_one_or_none()
        return udt_name == "vector"

    async def replace_document(
        self,
        session: AsyncSession,
        metadata: DocumentMetadata,
        sections: Sequence[SectionRecord],
        section_embeddings: dict[str, list[float]],
        facts: Sequence[dict[str, object]],
        risks: Sequence[dict[str, object]],
    ) -> None:
        await session.execute(delete(document_facts).where(document_facts.c.document_id == metadata.document_id))
        await session.execute(delete(document_risks).where(document_risks.c.document_id == metadata.document_id))
        await session.execute(
            delete(document_sections).where(document_sections.c.document_id == metadata.document_id)
        )

        existing = await session.execute(
            select(documents.c.id).where(documents.c.id == metadata.document_id)
        )
        payload = {
            "id": metadata.document_id,
            "content_id": metadata.content_id,
            "pitch_id": metadata.pitch_id,
            "filename": metadata.filename,
            "document_type": metadata.doc_type.value,
            "title": metadata.title,
            "source_path": metadata.source_path,
            "parser_used": metadata.parser_used,
            "sectioning_hint": metadata.sectioning_hint.value,
            "ingestion_status": metadata.ingestion_status.value,
            "warnings_json": metadata.warnings,
            "errors_json": metadata.errors,
            "fallback_applied": metadata.fallback_applied,
            "source_metadata": metadata.source_metadata,
        }
        if existing.scalar_one_or_none() is None:
            await session.execute(insert(documents).values(payload))
        else:
            await session.execute(
                documents.update().where(documents.c.id == metadata.document_id).values(**payload)
            )

        if sections:
            if await self._embedding_column_is_vector(session):
                await session.execute(
                    text(
                        """
                        INSERT INTO document_sections (
                            id, document_id, section_key, title, section_type, content,
                            order_index, source_reference, structure_confidence, page_number,
                            clause_id, embedding_model, embedding, metadata_json
                        ) VALUES (
                            :id, :document_id, :section_key, :title, :section_type, :content,
                            :order_index, :source_reference, :structure_confidence, :page_number,
                            :clause_id, :embedding_model, CAST(:embedding AS vector), CAST(:metadata_json AS jsonb)
                        )
                        """
                    ),
                    [
                        {
                            "id": section.section_id,
                            "document_id": section.document_id,
                            "section_key": section.section_key,
                            "title": section.title,
                            "section_type": section.section_type,
                            "content": section.content,
                            "order_index": section.order_index,
                            "source_reference": section.source_reference,
                            "structure_confidence": section.structure_confidence,
                            "page_number": section.page_number,
                            "clause_id": section.clause_id,
                            "embedding_model": "hash-embedding-v1",
                            "embedding": str(section_embeddings.get(section.section_id)),
                            "metadata_json": json.dumps(section.metadata_json),
                        }
                        for section in sections
                    ],
                )
            else:
                await session.execute(
                    insert(document_sections),
                    [
                        {
                            "id": section.section_id,
                            "document_id": section.document_id,
                            "section_key": section.section_key,
                            "title": section.title,
                            "section_type": section.section_type,
                            "content": section.content,
                            "order_index": section.order_index,
                            "source_reference": section.source_reference,
                            "structure_confidence": section.structure_confidence,
                            "page_number": section.page_number,
                            "clause_id": section.clause_id,
                            "embedding_model": "hash-embedding-v1",
                            "embedding": section_embeddings.get(section.section_id),
                            "metadata_json": section.metadata_json,
                        }
                        for section in sections
                    ],
                )
        if facts:
            await session.execute(insert(document_facts), list(facts))
        if risks:
            await session.execute(
                insert(document_risks),
                [
                    {
                        "id": risk["id"],
                        "document_id": risk["document_id"],
                        "section_id": risk["section_id"],
                        "risk_type": risk["risk_type"],
                        "severity": risk["severity"],
                        "summary": risk["summary"],
                        "mitigation": risk["mitigation"],
                        "source_text": risk["source_text"],
                        "status": risk["status"],
                    }
                    for risk in risks
                ],
            )
        await session.commit()
