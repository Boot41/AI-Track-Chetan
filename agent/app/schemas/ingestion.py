from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    SCRIPT = "script"
    CONTRACT = "contract"
    DECK = "deck"
    REPORT = "report"
    MEMO = "memo"
    OTHER = "other"


class SectioningHint(StrEnum):
    SCRIPT_SCENE = "script_scene"
    CONTRACT_CLAUSE = "contract_clause"
    SLIDE = "slide"
    REPORT_SECTION = "report_section"
    MEMO_SECTION = "memo_section"
    HEADING_BLOCK = "heading_block"
    PARAGRAPH = "paragraph"


class IngestionStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class RetrievalMethod(StrEnum):
    FTS = "fts"
    VECTOR = "vector"
    HYBRID = "hybrid"
    SQL = "sql"
    DERIVED = "derived"


class RawDocumentRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    content_id: str = Field(min_length=1)
    pitch_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    title: str = Field(min_length=1)
    manifest_doc_type: str = Field(min_length=1)
    sectioning_hint: SectioningHint
    primary_use: str | None = None
    expected_entities: list[str] = Field(default_factory=list)
    expected_risks: list[str] = Field(default_factory=list)
    expected_signals: list[str] = Field(default_factory=list)


class DocumentClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    doc_type: DocumentType
    parser_used: str = Field(min_length=1)
    sectioning_hint: SectioningHint
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    content_id: str = Field(min_length=1)
    pitch_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    title: str = Field(min_length=1)
    doc_type: DocumentType
    sectioning_hint: SectioningHint
    parser_used: str = Field(min_length=1)
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    fallback_applied: bool = False
    source_metadata: dict[str, object] = Field(default_factory=dict)


class SectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    section_key: str = Field(min_length=1)
    title: str | None = None
    section_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    order_index: int = Field(ge=0)
    source_reference: str = Field(min_length=1)
    structure_confidence: float = Field(ge=0.0, le=1.0)
    page_number: int | None = None
    clause_id: str | None = None
    metadata_json: dict[str, object] = Field(default_factory=dict)


class IngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    content_id: str = Field(min_length=1)
    status: IngestionStatus
    parser_used: str = Field(min_length=1)
    sections_indexed: int = Field(ge=0)
    sections_failed: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    fallback_applied: bool = False
    facts_extracted: int = Field(ge=0, default=0)
    risks_extracted: int = Field(ge=0, default=0)


class IngestionInventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    manifest_path: str = Field(min_length=1)
    document_count: int = Field(ge=1)
    documents: list[RawDocumentRegistration] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class IngestionInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_root: str = Field(min_length=1)
    items: list[IngestionInventoryItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
