from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, Float, ForeignKey, Integer, MetaData, String, Table, Text

from app.persistence.vector_type import Vector

metadata = MetaData()

documents = Table(
    "documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("content_id", String(128)),
    Column("pitch_id", String(128)),
    Column("filename", String(255)),
    Column("document_type", String(64), nullable=False),
    Column("title", String(255), nullable=False),
    Column("source_path", String(500), nullable=False),
    Column("parser_used", String(64)),
    Column("sectioning_hint", String(64)),
    Column("ingestion_status", String(32), nullable=False),
    Column("warnings_json", JSON),
    Column("errors_json", JSON),
    Column("fallback_applied", Boolean, nullable=False),
    Column("source_metadata", JSON),
)

document_sections = Table(
    "document_sections",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("document_id", String(36), ForeignKey("documents.id"), nullable=False),
    Column("section_key", String(128), nullable=False),
    Column("title", String(255)),
    Column("section_type", String(64), nullable=False),
    Column("content", Text, nullable=False),
    Column("order_index", Integer, nullable=False),
    Column("source_reference", String(255), nullable=False),
    Column("structure_confidence", Float, nullable=False),
    Column("page_number", Integer),
    Column("clause_id", String(128)),
    Column("embedding_model", String(128)),
    Column("embedding", Vector(12)),
    Column("metadata_json", JSON),
)

document_facts = Table(
    "document_facts",
    metadata,
    Column("fact_id", String(36), primary_key=True),
    Column("document_id", String(36), ForeignKey("documents.id"), nullable=False),
    Column("section_id", String(36), ForeignKey("document_sections.id"), nullable=False),
    Column("subject", String(255), nullable=False),
    Column("predicate", String(255), nullable=False),
    Column("object_value", Text, nullable=False),
    Column("qualifier", String(255)),
    Column("source_text", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("extracted_by", String(128), nullable=False),
)

document_risks = Table(
    "document_risks",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("document_id", String(36), ForeignKey("documents.id"), nullable=False),
    Column("section_id", String(36), ForeignKey("document_sections.id"), nullable=False),
    Column("risk_type", String(128), nullable=False),
    Column("severity", String(32), nullable=False),
    Column("summary", Text, nullable=False),
    Column("mitigation", Text),
    Column("source_text", Text, nullable=False),
    Column("status", String(32), nullable=False),
)

structured_metrics = Table(
    "structured_metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("pitch_id", String(128), nullable=False),
    Column("metric_key", String(128), nullable=False),
    Column("metric_value", Float, nullable=False),
    Column("source_table", String(128), nullable=False),
    Column("source_reference", String(255), nullable=False),
)
