from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import agent_service_client, db_session
from app.auth.deps import require_user
from app.db.models import User
from app.schemas.chat_api import (
    ChatMessageCreateRequest,
    EvaluationHistoryResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDetail,
    SessionEvaluationsResponse,
    SessionMessagesResponse,
    SessionSummary,
)
from app.schemas.contracts import PublicResponseContract
from app.services.agent_proxy import AgentServiceClient
from app.services.chat import (
    create_message_and_evaluation,
    create_or_reuse_session,
    get_session_detail,
    list_evaluations,
    list_session_evaluations,
    list_session_messages,
    list_sessions,
)

router = APIRouter(tags=["chat"])


@router.post("/sessions", response_model=SessionCreateResponse)
async def upsert_session(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
) -> SessionCreateResponse:
    return await create_or_reuse_session(db, user, body)


@router.get("/sessions", response_model=list[SessionSummary])
async def get_sessions(
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
) -> list[SessionSummary]:
    return await list_sessions(db, user)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
) -> SessionDetail:
    return await get_session_detail(db, user, session_id)


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_messages(
    session_id: str,
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
) -> SessionMessagesResponse:
    return await list_session_messages(db, user, session_id)


@router.post("/sessions/{session_id}/messages", response_model=PublicResponseContract)
async def post_message(
    session_id: str,
    body: ChatMessageCreateRequest,
    request: Request,
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
    proxy: AgentServiceClient = Depends(agent_service_client),
) -> PublicResponseContract:
    request_id = getattr(request.state, "request_id", "missing-request-id")
    return await create_message_and_evaluation(db, user, session_id, body, proxy, request_id)


@router.get("/sessions/{session_id}/evaluations", response_model=SessionEvaluationsResponse)
async def get_session_history(
    session_id: str,
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
) -> SessionEvaluationsResponse:
    return await list_session_evaluations(db, user, session_id)


@router.get("/evaluations", response_model=EvaluationHistoryResponse)
async def get_evaluation_history(
    session_id: str | None = None,
    db: AsyncSession = Depends(db_session),
    user: User = Depends(require_user),
) -> EvaluationHistoryResponse:
    return await list_evaluations(db, user, session_id)
