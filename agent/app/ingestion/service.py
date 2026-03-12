from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from .classifiers import DocumentTypeClassifier
from .extractors import ContractFactExtractor, DocumentRiskExtractor
from .inventory import RAW_DATA_ROOT, build_ingestion_inventory
from .parsers import ParserRouter
from ..persistence.repository import DocumentRepository
from ..retrieval.embeddings import HashEmbeddingService
from ..schemas.ingestion import DocumentMetadata, IngestionResult, IngestionStatus


class DocumentIngestionService:
    def __init__(
        self,
        repository: DocumentRepository | None = None,
        classifier: DocumentTypeClassifier | None = None,
        parser_router: ParserRouter | None = None,
        embedding_service: HashEmbeddingService | None = None,
        fact_extractor: ContractFactExtractor | None = None,
        risk_extractor: DocumentRiskExtractor | None = None,
    ) -> None:
        self._repository = repository or DocumentRepository()
        self._classifier = classifier or DocumentTypeClassifier()
        self._parser_router = parser_router or ParserRouter()
        self._embedding_service = embedding_service or HashEmbeddingService()
        self._fact_extractor = fact_extractor or ContractFactExtractor()
        self._risk_extractor = risk_extractor or DocumentRiskExtractor()

    async def ingest_corpus(
        self,
        session: AsyncSession,
        raw_root: Path = RAW_DATA_ROOT,
    ) -> list[IngestionResult]:
        inventory = build_ingestion_inventory(raw_root)
        results: list[IngestionResult] = []
        for inventory_error in inventory.errors:
            results.append(
                IngestionResult(
                    document_id=f"inventory-error:{len(results) + 1}",
                    content_id="inventory",
                    status=IngestionStatus.FAILED,
                    parser_used="inventory_validation",
                    sections_indexed=0,
                    sections_failed=0,
                    warnings=list(inventory.warnings),
                    errors=[inventory_error],
                    fallback_applied=False,
                    facts_extracted=0,
                    risks_extracted=0,
                )
            )
        for item in inventory.items:
            item_warnings = list(item.warnings)
            item_errors = list(item.errors)
            for registration in item.documents:
                try:
                    classification = self._classifier.classify(registration)
                    content = Path(registration.source_path).read_text(encoding="utf-8")
                    parser = self._parser_router.get_parser(classification)
                    parsed = parser.parse(registration, classification, content)
                    metadata_errors = list(item_errors)
                    if not parsed.sections:
                        metadata_errors.append("No sections parsed")
                    metadata = DocumentMetadata(
                        document_id=registration.document_id,
                        content_id=registration.content_id,
                        pitch_id=registration.pitch_id,
                        source_path=registration.source_path,
                        filename=registration.filename,
                        title=registration.title,
                        doc_type=classification.doc_type,
                        sectioning_hint=classification.sectioning_hint,
                        parser_used=classification.parser_used,
                        ingestion_status=(
                            IngestionStatus.PARTIAL
                            if parsed.sections and (parsed.warnings or metadata_errors)
                            else (
                                IngestionStatus.SUCCESS
                                if parsed.sections
                                else IngestionStatus.FAILED
                            )
                        ),
                        warnings=[*item_warnings, *parsed.warnings],
                        errors=metadata_errors,
                        fallback_applied=parsed.fallback_applied,
                        source_metadata={
                            "manifest_doc_type": registration.manifest_doc_type,
                            "primary_use": registration.primary_use,
                            "expected_entities": registration.expected_entities,
                            "indexed_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
                        },
                    )
                    facts = self._fact_extractor.extract(classification, parsed.sections)
                    risks = self._risk_extractor.extract(classification, parsed.sections)
                    embeddings = self._embedding_service.embed_texts(
                        [section.content for section in parsed.sections]
                    )
                    embedding_map = {
                        section.section_id: embedding
                        for section, embedding in zip(parsed.sections, embeddings, strict=True)
                    }
                    await self._repository.replace_document(
                        session,
                        metadata,
                        parsed.sections,
                        embedding_map,
                        facts,
                        risks,
                    )
                    results.append(
                        IngestionResult(
                            document_id=registration.document_id,
                            content_id=registration.content_id,
                            status=metadata.ingestion_status,
                            parser_used=metadata.parser_used,
                            sections_indexed=len(parsed.sections),
                            sections_failed=0,
                            warnings=metadata.warnings,
                            errors=metadata.errors,
                            fallback_applied=metadata.fallback_applied,
                            facts_extracted=len(facts),
                            risks_extracted=len(risks),
                        )
                    )
                except Exception as exc:
                    results.append(
                        IngestionResult(
                            document_id=registration.document_id,
                            content_id=registration.content_id,
                            status=IngestionStatus.FAILED,
                            parser_used="unknown",
                            sections_indexed=0,
                            sections_failed=1,
                            warnings=item_warnings,
                            errors=[*item_errors, f"Unhandled ingestion failure: {exc}"],
                            fallback_applied=False,
                            facts_extracted=0,
                            risks_extracted=0,
                        )
                    )
        return results
