from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.routing_spec import ROUTING_SPEC
from app.db.models import ChatMessage, ChatSession, EvaluationResult, User
from app.schemas.chat_api import (
    ChatMessageCreateRequest,
    ChatMessageRecord,
    EvaluationHistoryResponse,
    PersistedEvaluationRecord,
    ProxyInvocationLog,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDetail,
    SessionEvaluationsResponse,
    SessionMessagesResponse,
    SessionSummary,
)
from app.schemas.contracts import (
    AgentRequestEnvelope,
    ComparisonState,
    PublicResponseContract,
    QueryClassification,
    QueryType,
    ScorecardType,
    SessionState,
    TrustedRequestContext,
)
from app.services.agent_proxy import AgentServiceClient


async def create_or_reuse_session(
    db: AsyncSession,
    user: User,
    body: SessionCreateRequest,
) -> SessionCreateResponse:
    if body.session_id:
        session = await _get_owned_session(db, user.id, body.session_id)
        logger.info(
            "session_reused user_id={} session_id={}",
            user.id,
            session.id,
        )
        return SessionCreateResponse(session=_to_session_detail(session), reused_existing=True)

    session_state = SessionState(pitch_id=body.pitch_id) if body.pitch_id else None
    session = ChatSession(
        user_id=user.id,
        title=body.title,
        comparison_enabled=body.comparison_enabled,
        session_state=session_state.model_dump() if session_state else None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info("session_created user_id={} session_id={}", user.id, session.id)
    return SessionCreateResponse(session=_to_session_detail(session), reused_existing=False)


async def list_sessions(db: AsyncSession, user: User) -> list[SessionSummary]:
    statement = (
        select(
            ChatSession,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )
    result = await db.execute(statement)
    sessions: list[SessionSummary] = []
    for session, message_count in result.all():
        sessions.append(
            SessionSummary(
                id=session.id,
                title=session.title,
                comparison_enabled=session.comparison_enabled,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=message_count,
                latest_query_type=_parse_query_type_from_state(session.session_state),
            )
        )
    return sessions


async def get_session_detail(db: AsyncSession, user: User, session_id: str) -> SessionDetail:
    session = await _get_owned_session(db, user.id, session_id)
    return _to_session_detail(session)


async def list_session_messages(
    db: AsyncSession,
    user: User,
    session_id: str,
) -> SessionMessagesResponse:
    session = await _get_owned_session(db, user.id, session_id)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = [_to_message_record(message) for message in result.scalars().all()]
    return SessionMessagesResponse(session=_to_session_detail(session), messages=messages)


async def list_session_evaluations(
    db: AsyncSession,
    user: User,
    session_id: str,
) -> SessionEvaluationsResponse:
    session = await _get_owned_session(db, user.id, session_id)
    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.session_id == session_id)
        .order_by(EvaluationResult.created_at.desc())
    )
    evaluations = [_to_evaluation_record(item) for item in result.scalars().all()]
    return SessionEvaluationsResponse(session=_to_session_detail(session), evaluations=evaluations)


async def list_evaluations(
    db: AsyncSession,
    user: User,
    session_id: str | None = None,
) -> EvaluationHistoryResponse:
    if session_id is not None:
        await _get_owned_session(db, user.id, session_id)
    statement = (
        select(EvaluationResult)
        .join(ChatSession, ChatSession.id == EvaluationResult.session_id)
        .where(ChatSession.user_id == user.id)
        .order_by(EvaluationResult.created_at.desc())
    )
    if session_id is not None:
        statement = statement.where(EvaluationResult.session_id == session_id)
    result = await db.execute(statement)
    evaluations = [_to_evaluation_record(item) for item in result.scalars().all()]
    return EvaluationHistoryResponse(evaluations=evaluations)


async def create_message_and_evaluation(
    db: AsyncSession,
    user: User,
    session_id: str,
    body: ChatMessageCreateRequest,
    agent_client: AgentServiceClient,
    request_id: str,
) -> PublicResponseContract:
    session = await _get_owned_session(db, user.id, session_id)
    classification = ROUTING_SPEC[body.query_type]

    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        message_text=body.message,
        query_type=body.query_type.value,
        classification=classification.model_dump(mode="json"),
    )
    db.add(user_message)
    session.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(user_message)

    session_state = _build_session_state(session, body)
    envelope = AgentRequestEnvelope(
        message=body.message,
        context=TrustedRequestContext(
            user_id=user.id,
            session_id=session.id,
            chat_message_id=user_message.id,
        ),
        session_state=session_state,
    )

    started_at = datetime.now(UTC)
    try:
        response = await agent_client.evaluate(envelope)
        response = PublicResponseContract.model_validate(response)
    except Exception:
        logger.exception(
            "agent_proxy_failed request_id={} user_id={} session_id={}",
            request_id,
            user.id,
            session.id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent service invocation failed",
        ) from None

    evaluation = EvaluationResult(
        session_id=session.id,
        message_id=user_message.id,
        query_type=response.scorecard.query_type.value,
        answer_text=response.answer,
        scorecard=response.scorecard.model_dump(mode="json"),
        evidence=[item.model_dump(mode="json") for item in response.evidence],
        meta=response.meta.model_dump(mode="json"),
        recommendation=response.scorecard.recommendation.value
        if response.scorecard.recommendation is not None
        else None,
        confidence=response.meta.confidence,
    )
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        message_text=response.answer,
        query_type=response.scorecard.query_type.value,
        classification=None,
    )
    session.session_state = _merge_session_state(session_state, response).model_dump(mode="json")
    session.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.add_all([evaluation, assistant_message])
    await db.commit()
    await db.refresh(evaluation)

    duration_ms = (datetime.now(UTC) - started_at).total_seconds() * 1000
    invocation_log = ProxyInvocationLog(
        request_id=request_id,
        user_id=user.id,
        session_id=session.id,
        query_type=body.query_type,
        agent_request=envelope,
        duration_ms=duration_ms,
        success=True,
        backend_mode="stub",
        persisted_evaluation_id=evaluation.id,
    )
    logger.info("agent_proxy_success {}", invocation_log.model_dump_json())
    logger.info(
        "persistence_success request_id={} session_id={} message_id={} evaluation_id={}",
        request_id,
        session.id,
        user_message.id,
        evaluation.id,
    )
    return response


async def _get_owned_session(db: AsyncSession, user_id: int, session_id: str) -> ChatSession:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .options(selectinload(ChatSession.messages), selectinload(ChatSession.evaluation_results))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _to_session_detail(session: ChatSession) -> SessionDetail:
    return SessionDetail(
        id=session.id,
        title=session.title,
        comparison_enabled=session.comparison_enabled,
        session_state=SessionState.model_validate(session.session_state)
        if session.session_state
        else None,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _to_message_record(message: ChatMessage) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        message_text=message.message_text,
        query_type=QueryType(message.query_type) if message.query_type else None,
        classification=QueryClassification.model_validate(message.classification)
        if message.classification
        else None,
        created_at=message.created_at,
    )


def _to_evaluation_record(result: EvaluationResult) -> PersistedEvaluationRecord:
    return PersistedEvaluationRecord(
        id=result.id,
        session_id=result.session_id,
        message_id=result.message_id,
        query_type=QueryType(result.query_type),
        created_at=result.created_at,
        response=PublicResponseContract.model_validate(
            {
                "answer": result.answer_text,
                "scorecard": result.scorecard,
                "evidence": result.evidence,
                "meta": result.meta,
            }
        ),
    )


def _build_session_state(session: ChatSession, body: ChatMessageCreateRequest) -> SessionState:
    previous_state = (
        SessionState.model_validate(session.session_state)
        if session.session_state
        else SessionState()
    )
    history = [*previous_state.conversation_intent_history, body.query_type]
    return previous_state.model_copy(
        update={
            "pitch_id": body.pitch_id or previous_state.pitch_id,
            "query_type": body.query_type,
            "conversation_intent_history": history,
        }
    )


def _merge_session_state(
    session_state: SessionState,
    response: PublicResponseContract,
) -> SessionState:
    comparison_state = session_state.comparison_state
    if (
        response.scorecard.scorecard_type == ScorecardType.COMPARISON
        and response.scorecard.comparison is not None
        and len(response.scorecard.comparison.options) >= 2
    ):
        comparison_state = ComparisonState(
            option_a=response.scorecard.comparison.options[0],
            option_b=response.scorecard.comparison.options[1],
            comparison_scorecard=response.scorecard.comparison,
            comparison_axes=response.scorecard.comparison.comparison_axes,
            active_option=response.scorecard.comparison.winning_option_id,
        )

    return SessionState.model_validate(
        session_state.model_dump(mode="json")
        | {
            "query_type": response.scorecard.query_type.value,
            "last_scorecard": response.scorecard.model_dump(mode="json"),
            "comparison_state": comparison_state.model_dump(mode="json")
            if comparison_state is not None
            else None,
            "active_option": comparison_state.active_option if comparison_state else None,
        }
    )


def _parse_query_type_from_state(state: dict[str, object] | None) -> QueryType | None:
    if state is None:
        return None
    value = state.get("query_type")
    return QueryType(value) if isinstance(value, str) else None
