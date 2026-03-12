from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.evals.judge import LLMClient, SemanticJudge


@pytest.fixture
def mock_llm():
    client = MagicMock(spec=LLMClient)
    client.generate = AsyncMock(return_value="""
{
    "faithfulness": {"score": 4, "rationale": "Good facts."},
    "helpfulness": {"score": 5, "rationale": "Very clear."}
}
""")
    return client


@pytest.mark.asyncio
async def test_semantic_judge_parses_json_response(mock_llm):
    judge = SemanticJudge(mock_llm)
    res = await judge.judge("Query", "Answer")
    
    assert res.faithfulness.score == 4
    assert res.helpfulness.score == 5
    assert res.faithfulness.rationale == "Good facts."


@pytest.mark.asyncio
async def test_semantic_judge_handles_malformed_json(mock_llm):
    mock_llm.generate.return_value = "This is not JSON"
    judge = SemanticJudge(mock_llm)
    
    with pytest.raises(ValueError, match="Could not find JSON"):
        await judge.judge("Query", "Answer")
