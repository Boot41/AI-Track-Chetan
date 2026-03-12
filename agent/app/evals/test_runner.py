from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.agents.orchestrator import AgentOrchestrator
from app.evals.judge import JudgeResponse, SemanticJudge
from app.evals.runner import EvalRunner
from app.schemas.eval_runner import EvalCase, JudgeScore
from app.schemas.orchestration import (
    AgentTarget,
    OrchestrationResult,
    QueryClassification,
    QueryType,
    RoutePlan,
    SessionState,
)


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock(spec=AgentOrchestrator)
    # Mocking orchestrate response using a real OrchestrationResult object with minimal data
    res = OrchestrationResult(
        classification=QueryClassification(
            query_type=QueryType.GENERAL_QUESTION,
            target_agents=[AgentTarget.DOCUMENT_RETRIEVAL],
            reuse_cached_outputs=False,
            requires_recomputation=True,
        ),
        route_plan=RoutePlan(
            query_type=QueryType.GENERAL_QUESTION,
            agent_sequence=[AgentTarget.DOCUMENT_RETRIEVAL],
        ),
        index_fingerprint="test-fingerprint",
    )
    orchestrator.orchestrate = AsyncMock(return_value=res)
    orchestrator.update_session_state = MagicMock(return_value=SessionState())
    return orchestrator


@pytest.fixture
def mock_judge():
    judge = MagicMock(spec=SemanticJudge)
    judge.judge = AsyncMock(return_value=JudgeResponse(
        faithfulness=JudgeScore(score=5, rationale="Perfectly faithful."),
        helpfulness=JudgeScore(score=5, rationale="Extremely helpful.")
    ))
    return judge


@pytest.mark.asyncio
async def test_runner_executes_case_and_computes_metrics(mock_orchestrator, mock_judge):
    runner = EvalRunner(mock_orchestrator, mock_judge)
    case = EvalCase(
        fixture_id="test-case-1",
        query="Should we greenlight project X?",
        pitch_id="pitch_x",
        required_evidence=[{"source_reference": "ref-1", "section_id": "sec-1"}]
    )
    
    result = await runner.run_case(case)
    
    assert result.fixture_id == "test-case-1"
    assert result.passed is True
    assert result.faithfulness.score == 5
    assert result.recall_at_5 == 0.0


@pytest.mark.asyncio
async def test_runner_handles_multi_turn_consistency(mock_orchestrator):
    runner = EvalRunner(mock_orchestrator)
    case = EvalCase(
        fixture_id="multi-turn-test",
        query="First turn?",
        multi_turn_sequence=["Second turn?"]
    )
    
    result = await runner.run_case(case)
    
    assert len(result.multi_turn_results) == 1
    assert mock_orchestrator.orchestrate.call_count == 2
