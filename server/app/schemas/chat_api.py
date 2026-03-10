from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contracts import (
    AgentRequestEnvelope,
    PublicResponseContract,
    QueryClassification,
    QueryType,
    SessionState,
)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    title: str | None = Field(default=None, max_length=255)
    comparison_enabled: bool = False
    pitch_id: str | None = None


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None = None
    comparison_enabled: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(ge=0)
    latest_query_type: QueryType | None = None


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None = None
    comparison_enabled: bool
    session_state: SessionState | None = None
    created_at: datetime
    updated_at: datetime


class SessionCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: SessionDetail
    reused_existing: bool


class ChatMessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    query_type: QueryType
    pitch_id: str | None = None


class ChatMessageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    role: MessageRole
    message_text: str
    query_type: QueryType | None = None
    classification: QueryClassification | None = None
    created_at: datetime


class PersistedEvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    message_id: str | None = None
    query_type: QueryType
    created_at: datetime
    response: PublicResponseContract


class SessionMessagesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: SessionDetail
    messages: list[ChatMessageRecord] = Field(default_factory=list)


class SessionEvaluationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: SessionDetail
    evaluations: list[PersistedEvaluationRecord] = Field(default_factory=list)


class EvaluationHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: list[PersistedEvaluationRecord] = Field(default_factory=list)


class ProxyInvocationLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    user_id: int
    session_id: str
    query_type: QueryType
    agent_request: AgentRequestEnvelope
    duration_ms: float = Field(ge=0.0)
    success: bool
    backend_mode: str
    persisted_evaluation_id: str | None = None
