from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ..schemas.eval_runner import JudgeScore


class JudgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faithfulness: JudgeScore
    helpfulness: JudgeScore


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> str: ...


class SemanticJudge:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def judge(
        self,
        query: str,
        answer: str,
        golden_answer: str | None = None,
        expected_risks: list[str] | None = None,
        expected_facts: list[str] | None = None,
    ) -> JudgeResponse:
        prompt = self._build_prompt(query, answer, golden_answer, expected_risks, expected_facts)
        response_text = await self.llm_client.generate(prompt)
        return self._parse_response(response_text)

    def _build_prompt(
        self,
        query: str,
        answer: str,
        golden_answer: str | None = None,
        expected_risks: list[str] | None = None,
        expected_facts: list[str] | None = None,
    ) -> str:
        prompt = """You are an expert judge evaluating an AI agent's response
for an OTT decision support system.
Evaluate the response based on faithfulness and helpfulness.

Query: {query}
Agent Answer: {answer}
"""
        prompt = prompt.format(query=query, answer=answer)
        if golden_answer:
            prompt += f"\nGolden Answer: {golden_answer}"
        if expected_risks:
            prompt += f"\nExpected Risks to mention: {', '.join(expected_risks)}"
        if expected_facts:
            prompt += f"\nExpected ROI Facts to mention: {', '.join(expected_facts)}"

        prompt += """
Return a JSON object with the following structure:
{
    "faithfulness": {"score": int (1-5), "rationale": "string"},
    "helpfulness": {"score": int (1-5), "rationale": "string"}
}

Faithfulness: Does the answer stick to the facts and avoid hallucinations?
Helpfulness: Does the answer address the user's query comprehensively and professionally?
"""
        return prompt

    def _parse_response(self, text: str) -> JudgeResponse:
        # Simple JSON extraction
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"Could not find JSON in judge response: {text}")
        data = json.loads(text[start:end])
        return JudgeResponse.model_validate(data)
