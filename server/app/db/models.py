from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.vector_type import Vector


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="user")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comparison_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    session_state: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="chat_sessions")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="session")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    message_text: Mapped[str] = mapped_column(Text)
    query_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="message")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("chat_messages.id"), nullable=True)
    query_type: Mapped[str] = mapped_column(String(64), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    scorecard: Mapped[dict[str, object]] = mapped_column(JSON)
    evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    meta: Mapped[dict[str, object]] = mapped_column(JSON)
    recommendation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="evaluation_results")
    message: Mapped[ChatMessage | None] = relationship(back_populates="evaluation_results")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    content_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    pitch_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(500), unique=True)
    parser_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sectioning_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingestion_status: Mapped[str] = mapped_column(String(32), default="pending")
    warnings_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    errors_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    fallback_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    source_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sections: Mapped[list[DocumentSection]] = relationship(back_populates="document")
    facts: Mapped[list[DocumentFact]] = relationship(back_populates="document")
    risks: Mapped[list[DocumentRisk]] = relationship(back_populates="document")


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    section_key: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_type: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    source_reference: Mapped[str] = mapped_column(String(255), index=True)
    structure_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clause_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(12), nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="sections")
    facts: Mapped[list[DocumentFact]] = relationship(back_populates="section")
    risks: Mapped[list[DocumentRisk]] = relationship(back_populates="section")


class DocumentFact(Base):
    __tablename__ = "document_facts"

    fact_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("document_sections.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    predicate: Mapped[str] = mapped_column(String(255))
    object_value: Mapped[str] = mapped_column(Text)
    qualifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    extracted_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="facts")
    section: Mapped[DocumentSection] = relationship(back_populates="facts")


class DocumentRisk(Base):
    __tablename__ = "document_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("document_sections.id"), index=True)
    risk_type: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(Text)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="risks")
    section: Mapped[DocumentSection] = relationship(back_populates="risks")
