from __future__ import annotations

from pydantic import ValidationError

from app.schemas.chat_api import ChatMessageCreateRequest, SessionCreateRequest
from app.schemas.contracts import QueryType, ScorecardType
from app.services.agent_proxy import StubAgentServiceClient


def test_session_create_request_forbids_unknown_fields() -> None:
    try:
        SessionCreateRequest.model_validate({"title": "A", "unknown": True})
    except ValidationError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("SessionCreateRequest accepted an unknown field")


def test_chat_message_request_requires_query_type() -> None:
    try:
        ChatMessageCreateRequest.model_validate({"message": "Evaluate this"})
    except ValidationError as exc:
        assert "query_type" in str(exc)
    else:
        raise AssertionError("ChatMessageCreateRequest accepted a missing query_type")


async def test_stub_agent_client_adapts_comparison_fixture() -> None:
    client = StubAgentServiceClient()
    response = await client.evaluate(
        {
            "message": "Compare both options",
            "context": {"user_id": 1, "session_id": "sess-1"},
            "session_state": {"query_type": QueryType.COMPARISON.value},
        }
    )

    assert response.scorecard.scorecard_type == ScorecardType.COMPARISON
    assert response.scorecard.query_type == QueryType.COMPARISON
    assert response.scorecard.comparison is not None
