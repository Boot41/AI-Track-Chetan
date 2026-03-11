from __future__ import annotations

import json

from agent.app.ingestion.service import DocumentIngestionService
from agent.app.persistence.tables import (
    document_facts,
    document_risks,
    document_sections,
    documents,
)
from agent.app.retrieval.hybrid import HybridRetriever
from agent.app.schemas.ingestion import DocumentType
from agent.app.schemas.retrieval import RetrievalQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_full_ingestion_persists_documents_sections_facts_and_risks(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    results = await DocumentIngestionService().ingest_corpus(db)

    assert len(results) == 20
    assert all(result.sections_indexed > 0 for result in results)

    document_count = await db.scalar(select(func.count()).select_from(documents))
    section_count = await db.scalar(select(func.count()).select_from(document_sections))
    fact_count = await db.scalar(select(func.count()).select_from(document_facts))
    risk_count = await db.scalar(select(func.count()).select_from(document_risks))

    assert document_count == 20
    assert section_count and section_count > 20
    assert fact_count and fact_count > 0
    assert risk_count and risk_count > 0

    retriever = HybridRetriever(session_factory)
    clause_results = await retriever.retrieve(
        RetrievalQuery(
            query_text="matching rights spin-off sequel prequel",
            content_ids=["pitch_shadow_protocol"],
            document_types=[DocumentType.CONTRACT],
            limit=3,
            per_document_type_weight={DocumentType.CONTRACT: 1.2},
        )
    )
    assert clause_results
    assert clause_results[0].source_reference.endswith("#clause-14.3")

    scene_results = await retriever.retrieve(
        RetrievalQuery(
            query_text="analog key digital problem bunker father",
            content_ids=["pitch_shadow_protocol"],
            document_types=[DocumentType.SCRIPT],
            limit=3,
            per_document_type_weight={DocumentType.SCRIPT: 1.1},
        )
    )
    assert scene_results
    assert any(result.source_reference.endswith("#scene-10") for result in scene_results)

    regulatory_results = await retriever.retrieve(
        RetrievalQuery(
            query_text="regulatory uncertainty censorship phased rollout",
            content_ids=["pitch_red_harbor"],
            limit=3,
            per_document_type_weight={DocumentType.REPORT: 1.0, DocumentType.CONTRACT: 1.1},
        )
    )
    assert regulatory_results
    assert any(
        result.source_reference.startswith("10_regulatory_risk_note.md")
        for result in regulatory_results
    )


async def test_partial_ingestion_fallback_is_traceable(db: AsyncSession) -> None:
    from pathlib import Path

    service = DocumentIngestionService()
    temp_root = Path("server/tests/.tmp_raw_fallback")
    temp_pitch = temp_root / "pitch_test_fallback"
    temp_pitch.mkdir(parents=True, exist_ok=True)
    (temp_pitch / "01_unstructured_note.md").write_text(
        "single paragraph without headings but with censorship and regulatory uncertainty",
        encoding="utf-8",
    )
    (temp_pitch / "manifest.json").write_text(
        json.dumps(
            {
                "content_id": "pitch_test_fallback",
                "title": "Fallback Test",
                "documents": [
                    {
                        "filename": "01_unstructured_note.md",
                        "doc_type": "Strategic Analysis",
                        "title": "Fallback Note",
                        "sectioning_hint": "memo_section",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        inventory_results = await service.ingest_corpus(db, raw_root=temp_root)
    finally:
        for path in sorted(temp_pitch.glob("*"), reverse=True):
            path.unlink()
        temp_pitch.rmdir()
        temp_root.rmdir()

    assert inventory_results[0].fallback_applied is True
    assert inventory_results[0].warnings


async def test_ingestion_continues_when_one_document_fails(db: AsyncSession) -> None:
    from pathlib import Path

    service = DocumentIngestionService()
    temp_root = Path("server/tests/.tmp_raw_partial_failure")
    temp_pitch = temp_root / "pitch_partial_failure"
    temp_pitch.mkdir(parents=True, exist_ok=True)
    (temp_pitch / "01_valid_note.md").write_text(
        "## Section\n\nThis is valid markdown content for indexing.",
        encoding="utf-8",
    )
    (temp_pitch / "manifest.json").write_text(
        json.dumps(
            {
                "content_id": "pitch_partial_failure",
                "title": "Partial Failure",
                "documents": [
                    {
                        "filename": "01_valid_note.md",
                        "doc_type": "Strategic Analysis",
                        "title": "Valid Doc",
                        "sectioning_hint": "memo_section",
                    },
                    {
                        "filename": "02_missing_note.md",
                        "doc_type": "Strategic Analysis",
                        "title": "Missing Doc",
                        "sectioning_hint": "memo_section",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    try:
        results = await service.ingest_corpus(db, raw_root=temp_root)
    finally:
        for path in sorted(temp_pitch.glob("*"), reverse=True):
            path.unlink()
        temp_pitch.rmdir()
        temp_root.rmdir()

    assert len(results) == 1
    assert results[0].status.value == "partial"
    assert any("listed in manifest but file is missing" in error for error in results[0].errors)
