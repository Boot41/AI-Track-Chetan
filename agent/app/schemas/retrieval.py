from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingestion import DocumentType, RetrievalMethod


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=1)
    content_ids: list[str] = Field(default_factory=list)
    document_types: list[DocumentType] = Field(default_factory=list)
    source_paths: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=25)
    per_document_type_weight: dict[DocumentType, float] = Field(default_factory=dict)


class RetrievalCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    retrieval_method: RetrievalMethod
    confidence_score: float = Field(ge=0.0, le=1.0)
    document_type: DocumentType
    claim_support_metadata: dict[str, object] = Field(default_factory=dict)
