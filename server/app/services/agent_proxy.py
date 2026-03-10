from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.schemas.contracts import (
    AgentRequestEnvelope,
    ComparisonAxis,
    PublicResponseContract,
    QueryType,
    ScorecardType,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PHASE0_FIXTURE_DIR = REPO_ROOT / "client" / "src" / "fixtures" / "phase0"


class AgentServiceClient(Protocol):
    async def evaluate(self, envelope: AgentRequestEnvelope) -> PublicResponseContract: ...


class StubAgentServiceClient:
    """Phase 1 stub that returns Phase 0 public fixtures via a service boundary."""

    def __init__(self, fixture_dir: Path = PHASE0_FIXTURE_DIR) -> None:
        self._fixture_dir = fixture_dir

    async def evaluate(self, envelope: AgentRequestEnvelope) -> PublicResponseContract:
        envelope = AgentRequestEnvelope.model_validate(envelope)
        query_type = envelope.session_state.query_type if envelope.session_state else None
        if query_type is None:
            raise ValueError("session_state.query_type is required for stubbed agent calls")

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
