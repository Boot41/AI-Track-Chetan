from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Protocol

from app.schemas.contracts import (
    AgentRequestEnvelope,
    ComparisonAxis,
    PublicResponseContract,
    QueryType,
    ScorecardType,
    SessionState,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_RESPONSE_FIXTURE_DIR = REPO_ROOT / "server" / "app" / "fixtures" / "public_responses"


class AgentServiceClient(Protocol):
    async def evaluate(self, envelope: AgentRequestEnvelope) -> PublicResponseContract: ...


def _ensure_repo_root_on_path() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.append(repo_root)


def _to_orchestrator_session_state(
    state: SessionState | None,
) -> dict[str, Any] | None:
    if state is None:
        return None
    payload = {
        "pitch_id": state.pitch_id,
        "query_type": state.query_type.value if state.query_type is not None else None,
        "narrative_output": (
            {**state.narrative_output.model_dump(mode="json"), "payload": {}}
            if state.narrative_output is not None
            else None
        ),
        "roi_output": (
            {**state.roi_output.model_dump(mode="json"), "payload": {}}
            if state.roi_output is not None
            else None
        ),
        "risk_output": (
            {**state.risk_output.model_dump(mode="json"), "payload": {}}
            if state.risk_output is not None
            else None
        ),
        "catalog_output": (
            {**state.catalog_output.model_dump(mode="json"), "payload": {}}
            if state.catalog_output is not None
            else None
        ),
        "retrieval_context": state.retrieval_context,
        "conversation_intent_history": [item.value for item in state.conversation_intent_history],
        "comparison_state": (
            {
                "option_a": {
                    "option_id": state.comparison_state.option_a.option_id,
                    "label": state.comparison_state.option_a.label,
                    "query_type": state.comparison_state.option_a.query_type.value,
                },
                "option_b": {
                    "option_id": state.comparison_state.option_b.option_id,
                    "label": state.comparison_state.option_b.label,
                    "query_type": state.comparison_state.option_b.query_type.value,
                },
                "comparison_axes": [axis.value for axis in state.comparison_state.comparison_axes],
                "active_option": state.comparison_state.active_option,
            }
            if state.comparison_state is not None
            else None
        ),
        "active_option": state.active_option,
    }
    return payload


def _previous_scorecard(state: SessionState | None) -> dict[str, object] | None:
    if state is None:
        return None
    if state.last_scorecard is None:
        return None
    return state.last_scorecard.model_dump(mode="json")


def _comparison_state(state: SessionState | None) -> dict[str, object] | None:
    if state is None:
        return None
    if state.comparison_state is None:
        return None
    return state.comparison_state.model_dump(mode="json")


class OrchestratorAgentServiceClient:
    """HTTP client for the standalone Agent Service running on port 8020."""

    def __init__(self, base_url: str = "http://localhost:8020") -> None:
        self.base_url = base_url

    async def evaluate(self, envelope: AgentRequestEnvelope) -> PublicResponseContract:
        import httpx
        from app.schemas.contracts import PublicResponseContract

        envelope = AgentRequestEnvelope.model_validate(envelope)
        
        # Adapt internal envelope to Agent Service request
        payload = {
            "message": envelope.message,
            "user_id": str(envelope.context.user_id),
            "session_id": envelope.context.session_id,
            "context": {
                "chat_message_id": envelope.context.chat_message_id,
                "evaluation_id": envelope.context.evaluation_id,
                "session_state_payload": _to_orchestrator_session_state(envelope.session_state)
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/evaluate", json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Agent Service error: {response.text}")
            
            return PublicResponseContract.model_validate(response.json())


class StubAgentServiceClient:
    """Phase 1 stub that returns Phase 0 public fixtures via a service boundary."""

    def __init__(self, fixture_dir: Path = PUBLIC_RESPONSE_FIXTURE_DIR) -> None:
        self._fixture_dir = fixture_dir

    async def evaluate(self, envelope: AgentRequestEnvelope) -> PublicResponseContract:
        envelope = AgentRequestEnvelope.model_validate(envelope)
        query_type = envelope.session_state.query_type if envelope.session_state else None
        if query_type is None:
            query_type = QueryType.GENERAL_QUESTION

        response = self._load_base_response(query_type)
        return self._adapt_response(query_type, response)

    def _load_base_response(self, query_type: QueryType) -> PublicResponseContract:
        fixture_name = self._fixture_name_for_query_type(query_type)
        payload = json.loads((self._fixture_dir / fixture_name).read_text(encoding="utf-8"))
        return PublicResponseContract.model_validate(payload)

    def _fixture_name_for_query_type(self, query_type: QueryType) -> str:
        if query_type == QueryType.COMPARISON:
            return "comparison_response.json"
        if query_type in {
            QueryType.FOLLOWUP_WHY_NARRATIVE,
            QueryType.FOLLOWUP_WHY_ROI,
            QueryType.FOLLOWUP_WHY_RISK,
            QueryType.FOLLOWUP_WHY_CATALOG,
            QueryType.SCENARIO_CHANGE_BUDGET,
            QueryType.SCENARIO_CHANGE_LOCALIZATION,
            QueryType.GENERAL_QUESTION,
        }:
            return "followup_response.json"
        return "standard_evaluation_response.json"

    def _adapt_response(
        self,
        query_type: QueryType,
        response: PublicResponseContract,
    ) -> PublicResponseContract:
        payload = response.model_dump()
        payload["scorecard"]["query_type"] = query_type.value

        if query_type == QueryType.COMPARISON:
            payload["scorecard"]["scorecard_type"] = ScorecardType.COMPARISON.value
            payload["scorecard"]["focus_area"] = None
        elif query_type in {
            QueryType.FOLLOWUP_WHY_NARRATIVE,
            QueryType.FOLLOWUP_WHY_ROI,
            QueryType.FOLLOWUP_WHY_RISK,
            QueryType.FOLLOWUP_WHY_CATALOG,
        }:
            payload["scorecard"]["scorecard_type"] = ScorecardType.FOLLOWUP.value
            payload["scorecard"]["comparison"] = None
            payload["scorecard"]["focus_area"] = self._focus_area_for_query_type(query_type)
        else:
            payload["scorecard"]["scorecard_type"] = ScorecardType.EVALUATION.value
            payload["scorecard"]["comparison"] = None
            payload["scorecard"]["focus_area"] = None

        return PublicResponseContract.model_validate(payload)

    def _focus_area_for_query_type(self, query_type: QueryType) -> str | None:
        focus_map = {
            QueryType.FOLLOWUP_WHY_NARRATIVE: ComparisonAxis.NARRATIVE.value,
            QueryType.FOLLOWUP_WHY_ROI: ComparisonAxis.ROI.value,
            QueryType.FOLLOWUP_WHY_RISK: ComparisonAxis.RISK.value,
            QueryType.FOLLOWUP_WHY_CATALOG: ComparisonAxis.CATALOG_FIT.value,
        }
        return focus_map.get(query_type)
