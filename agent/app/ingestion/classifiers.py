from __future__ import annotations

from ..schemas.ingestion import (
    DocumentClassification,
    DocumentType,
    RawDocumentRegistration,
    SectioningHint,
)


class DocumentTypeClassifier:
    """Classify using manifest metadata first and filename hints second."""

    _MANIFEST_TYPE_MAP: dict[str, DocumentType] = {
        "creative script": DocumentType.SCRIPT,
        "legal agreement": DocumentType.CONTRACT,
        "legal summary": DocumentType.CONTRACT,
        "visual/marketing deck": DocumentType.DECK,
        "strategic analysis": DocumentType.MEMO,
    }

    _FILENAME_HINTS: tuple[tuple[str, DocumentType], ...] = (
        ("script", DocumentType.SCRIPT),
        ("contract", DocumentType.CONTRACT),
        ("term_sheet", DocumentType.CONTRACT),
        ("deck", DocumentType.DECK),
        ("memo", DocumentType.MEMO),
        ("report", DocumentType.REPORT),
    )

    def classify(self, registration: RawDocumentRegistration) -> DocumentClassification:
        manifest_value = registration.manifest_doc_type.strip().lower()
        doc_type = self._MANIFEST_TYPE_MAP.get(manifest_value)
        rationale = f"manifest doc_type={registration.manifest_doc_type}"
        confidence = 0.95

        if doc_type is None:
            for hint, candidate in self._FILENAME_HINTS:
                if hint in registration.filename.lower():
                    doc_type = candidate
                    rationale = f"filename hint matched {hint}"
                    confidence = 0.72
                    break

        if doc_type is None:
            if registration.sectioning_hint == SectioningHint.CONTRACT_CLAUSE:
                doc_type = DocumentType.CONTRACT
            elif registration.sectioning_hint == SectioningHint.SCRIPT_SCENE:
                doc_type = DocumentType.SCRIPT
            elif registration.sectioning_hint == SectioningHint.SLIDE:
                doc_type = DocumentType.DECK
            elif registration.sectioning_hint == SectioningHint.MEMO_SECTION:
                doc_type = DocumentType.MEMO
            else:
                doc_type = DocumentType.REPORT
            rationale = f"sectioning_hint={registration.sectioning_hint.value}"
            confidence = 0.66

        parser_used = {
            DocumentType.SCRIPT: "ScriptParser",
            DocumentType.CONTRACT: "ContractParser",
            DocumentType.DECK: "DeckParser",
            DocumentType.MEMO: "ReportParser",
            DocumentType.REPORT: "ReportParser",
            DocumentType.OTHER: "ReportParser",
        }[doc_type]

        return DocumentClassification(
            document_id=registration.document_id,
            doc_type=doc_type,
            parser_used=parser_used,
            sectioning_hint=registration.sectioning_hint,
            confidence=confidence,
            rationale=rationale,
        )
