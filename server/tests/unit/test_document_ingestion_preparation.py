from __future__ import annotations

from pathlib import Path

from agent.app.ingestion.classifiers import DocumentTypeClassifier
from agent.app.ingestion.inventory import build_ingestion_inventory
from agent.app.schemas.ingestion import DocumentType, SectioningHint


def test_raw_manifest_inventory_is_phase2_ready() -> None:
    inventory = build_ingestion_inventory()
    assert inventory.errors == []
    assert len(inventory.items) >= 2
    assert all(item.document_count > 0 for item in inventory.items)


def test_manifest_files_match_actual_documents() -> None:
    inventory = build_ingestion_inventory()
    registered_paths = {
        Path(document.source_path).resolve()
        for item in inventory.items
        for document in item.documents
    }
    actual_paths = {
        path.resolve()
        for item in inventory.items
        for path in Path(item.manifest_path).parent.glob("*.md")
        if path.name != "manifest.md"
    }
    assert registered_paths == actual_paths


def test_manifest_sectioning_hints_are_valid() -> None:
    inventory = build_ingestion_inventory()
    allowed = {
        SectioningHint.SCRIPT_SCENE,
        SectioningHint.CONTRACT_CLAUSE,
        SectioningHint.SLIDE,
        SectioningHint.REPORT_SECTION,
        SectioningHint.MEMO_SECTION,
    }
    seen = {document.sectioning_hint for item in inventory.items for document in item.documents}
    assert seen <= allowed


def test_classifier_prefers_manifest_metadata() -> None:
    inventory = build_ingestion_inventory()
    script_doc = next(
        document
        for item in inventory.items
        for document in item.documents
        if document.filename == "02_pilot_script.md"
    )
    memo_doc = next(
        document
        for item in inventory.items
        for document in item.documents
        if document.filename == "07_strategic_fit_memo.md"
    )
    classifier = DocumentTypeClassifier()

    script_classification = classifier.classify(script_doc)
    memo_classification = classifier.classify(memo_doc)

    assert script_classification.doc_type == DocumentType.SCRIPT
    assert script_classification.parser_used == "ScriptParser"
    assert memo_classification.doc_type == DocumentType.MEMO
    assert memo_classification.parser_used == "ReportParser"
