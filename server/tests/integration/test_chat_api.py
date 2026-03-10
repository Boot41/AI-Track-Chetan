from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import agent_service_client
from app.schemas.contracts import AgentRequestEnvelope, PublicResponseContract
from app.services.agent_proxy import StubAgentServiceClient


@pytest.mark.asyncio
async def test_sessions_route_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/sessions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_and_reuse_session(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/api/v1/sessions",
        json={"title": "Neon Shore", "comparison_enabled": True, "pitch_id": "pitch-neon-shore"},
        headers=auth_headers,
    )

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["reused_existing"] is False
    assert payload["session"]["comparison_enabled"] is True
    assert payload["session"]["session_state"]["pitch_id"] == "pitch-neon-shore"

    reuse_response = await client.post(
        "/api/v1/sessions",
        json={"session_id": payload["session"]["id"]},
        headers=auth_headers,
    )
    assert reuse_response.status_code == 200
    assert reuse_response.json()["reused_existing"] is True


@pytest.mark.asyncio
async def test_post_message_persists_messages_and_evaluations(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    session_response = await client.post(
        "/api/v1/sessions",
        json={"title": "Original Eval"},
        headers=auth_headers,
    )
    session_id = session_response.json()["session"]["id"]

    message_response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={
            "message": "Should we greenlight Neon Shore?",
            "query_type": "original_eval",
            "pitch_id": "pitch-neon-shore",
        },
        headers=auth_headers,
    )

    assert message_response.status_code == 200
    public_response = PublicResponseContract.model_validate(message_response.json())
    assert public_response.scorecard.query_type.value == "original_eval"
    assert set(public_response.meta.model_dump()) == {"warnings", "confidence", "review_required"}
    assert "X-Request-ID" in message_response.headers

    messages_response = await client.get(
        f"/api/v1/sessions/{session_id}/messages",
        headers=auth_headers,
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["classification"]["query_type"] == "original_eval"
    assert messages[1]["role"] == "assistant"

    evaluations_response = await client.get(
        f"/api/v1/sessions/{session_id}/evaluations",
        headers=auth_headers,
    )
    assert evaluations_response.status_code == 200
    evaluations = evaluations_response.json()["evaluations"]
    assert len(evaluations) == 1
    assert evaluations[0]["response"]["scorecard"]["scorecard_type"] == "evaluation"
    assert evaluations[0]["response"]["answer"]

    history_response = await client.get("/api/v1/evaluations", headers=auth_headers)
    assert history_response.status_code == 200
    assert len(history_response.json()["evaluations"]) == 1


@pytest.mark.asyncio
async def test_comparison_session_persists_comparison_shape(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    session_response = await client.post(
        "/api/v1/sessions",
        json={"title": "Comparison", "comparison_enabled": True},
        headers=auth_headers,
    )
    session_id = session_response.json()["session"]["id"]

    message_response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "Compare Neon Shore and Midnight Courts", "query_type": "comparison"},
        headers=auth_headers,
    )

    assert message_response.status_code == 200
    payload = message_response.json()
    assert payload["scorecard"]["scorecard_type"] == "comparison"
    assert payload["scorecard"]["comparison"]["winning_option_id"] == "catalog-midnight-courts"

    session_detail = await client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers)
    assert session_detail.status_code == 200
    assert session_detail.json()["session_state"]["comparison_state"]["active_option"] == (
        "catalog-midnight-courts"
    )


@pytest.mark.asyncio
async def test_invalid_chat_request_is_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    session_response = await client.post(
        "/api/v1/sessions",
        json={"title": "Validation"},
        headers=auth_headers,
    )
    session_id = session_response.json()["session"]["id"]

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "Missing query type"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_proxy_failures_return_bad_gateway(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_app: FastAPI,
) -> None:
    class FailingProxy:
        async def evaluate(self, envelope):  # type: ignore[no-untyped-def]
            raise RuntimeError("proxy down")

    test_app.dependency_overrides[agent_service_client] = lambda: FailingProxy()
    session_response = await client.post(
        "/api/v1/sessions",
        json={"title": "Failure path"},
        headers=auth_headers,
    )
    session_id = session_response.json()["session"]["id"]

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "Should fail", "query_type": "original_eval"},
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Agent service invocation failed"
    test_app.dependency_overrides.pop(agent_service_client, None)


@pytest.mark.asyncio
async def test_stub_proxy_dependency_returns_phase0_contract() -> None:
    response = await StubAgentServiceClient().evaluate(
        AgentRequestEnvelope.model_validate(
            {
                "message": "Should we buy this?",
                "context": {"user_id": 1, "session_id": "sess-1"},
                "session_state": {"query_type": "acquisition_eval"},
            }
        )
    )
    assert response.scorecard.query_type.value == "acquisition_eval"
