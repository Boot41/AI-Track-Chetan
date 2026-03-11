from __future__ import annotations

from pathlib import Path

from agent.app.ingestion.classifiers import DocumentTypeClassifier
from agent.app.ingestion.extractors import ContractFactExtractor, DocumentRiskExtractor
from agent.app.ingestion.inventory import build_ingestion_inventory
from agent.app.ingestion.parsers import (
    ContractParser,
    DeckParser,
    ParserRouter,
    ReportParser,
    ScriptParser,
)
from agent.app.retrieval.ranking import reciprocal_rank_fusion, rerank_candidates
from agent.app.schemas.ingestion import RetrievalMethod
from agent.app.schemas.retrieval import RetrievalCandidate


def _registration(filename: str):  # type: ignore[no-untyped-def]
    inventory = build_ingestion_inventory()
    return next(
        document
        for item in inventory.items
        for document in item.documents
        if document.filename == filename
    )


def _parse(filename: str):  # type: ignore[no-untyped-def]
    registration = _registration(filename)
    classification = DocumentTypeClassifier().classify(registration)
    parser = ParserRouter().get_parser(classification)
    content = Path(registration.source_path).read_text(encoding="utf-8")
    return parser.parse(registration, classification, content), classification


def test_script_parser_sections_by_scene() -> None:
    parsed, _classification = _parse("02_pilot_script.md")
    assert isinstance(ScriptParser().name, str)
    assert parsed.fallback_applied is False
    assert parsed.sections[0].source_reference.endswith("#scene-1")
    assert parsed.sections[0].metadata_json["scene_id"] == "1"
    assert len(parsed.sections) >= 10


def test_contract_parser_sections_by_clause() -> None:
    parsed, _classification = _parse("10_licensing_contract.md")
    clause_ids = {section.clause_id for section in parsed.sections}
    assert isinstance(ContractParser().name, str)
    assert "14.3" in clause_ids
    assert "14.5" in clause_ids
    assert any(section.source_reference.endswith("#clause-14.3") for section in parsed.sections)


def test_deck_parser_sections_by_slide() -> None:
    parsed, _classification = _parse("04_pitch_deck.md")
    assert isinstance(DeckParser().name, str)
    assert len(parsed.sections) == 10
    assert parsed.sections[0].metadata_json["slide_number"] == 1


def test_report_parser_sections_by_headings() -> None:
    parsed, classification = _parse("07_strategic_fit_memo.md")
    assert isinstance(ReportParser().name, str)
    assert classification.parser_used == "ReportParser"
    assert parsed.sections[0].section_type == "memo_section"
    assert any(section.title == "Genre Gap Rationale" for section in parsed.sections)


def test_parser_fallback_uses_low_structure_chunks() -> None:
    registration = _registration("01_pitch_overview.md")
    classification = DocumentTypeClassifier().classify(registration)
    parsed = ReportParser().parse(
        registration, classification, "single paragraph without markdown headings"
    )
    assert parsed.fallback_applied is True
    assert parsed.sections[0].structure_confidence < 0.5


def test_contract_fact_extraction_is_deterministic_and_narrow() -> None:
    parsed, classification = _parse("10_licensing_contract.md")
    facts = ContractFactExtractor().extract(classification, parsed.sections)
    predicates = {fact["predicate"] for fact in facts}
    assert {
        "rights_granted",
        "territory_scope",
        "exclusivity_window",
        "matching_rights",
        "localization_obligation",
        "term_length",
    } <= predicates


def test_risk_extraction_finds_contract_and_regulatory_risks() -> None:
    contract_parsed, contract_classification = _parse("04_licensing_contract.md")
    report_parsed, report_classification = _parse("10_regulatory_risk_note.md")
    extractor = DocumentRiskExtractor()

    contract_risks = extractor.extract(contract_classification, contract_parsed.sections)
    report_risks = extractor.extract(report_classification, report_parsed.sections)

    assert any(risk["risk_type"] == "exclusivity_overlap" for risk in contract_risks)
    assert any(risk["risk_type"] == "regulatory_uncertainty" for risk in report_risks)


def test_rrf_and_reranking_respect_fusion_and_confidence() -> None:
    scores = reciprocal_rank_fusion(
        [["a", "b", "c"], ["b", "c", "a"]],
        per_item_weight={"a": 1.0, "b": 1.2, "c": 0.8},
    )
    ranked = rerank_candidates(
        [
            {
                "section_id": "a",
                "fusion_score": scores["a"],
                "structure_confidence": 0.9,
                "method_score": 0.5,
            },
            {
                "section_id": "b",
                "fusion_score": scores["b"],
                "structure_confidence": 0.8,
                "method_score": 0.7,
            },
            {
                "section_id": "c",
                "fusion_score": scores["c"],
                "structure_confidence": 0.7,
                "method_score": 0.4,
            },
        ],
        limit=2,
    )
    assert ranked[0]["section_id"] == "b"
    assert len(ranked) == 2


def test_retrieval_candidate_schema_accepts_evidence_ready_payload() -> None:
    candidate = RetrievalCandidate(
        document_id="doc-1",
        section_id="sec-1",
        snippet="Matching-rights clause requires negotiation in good faith.",
        source_reference="10_licensing_contract.md#clause-14.3",
        retrieval_method=RetrievalMethod.HYBRID,
        confidence_score=0.82,
        document_type="contract",
        claim_support_metadata={"matched_methods": ["fts", "vector"]},
    )
    assert candidate.retrieval_method == RetrievalMethod.HYBRID
