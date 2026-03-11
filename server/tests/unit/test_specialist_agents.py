from __future__ import annotations

import pytest
from agent.app.agents.subagents import (
    CatalogFitAgent,
    DocumentRetrievalAgent,
    NarrativeAnalysisAgent,
    RiskContractAnalysisAgent,
    RoiPredictionAgent,
)
from agent.app.schemas.evaluation import RetrievalFocus, RiskSeverity
from agent.app.schemas.ingestion import DocumentType, RetrievalMethod
from agent.app.schemas.orchestration import (
    AgentExecutionContext,
    AgentRequest,
    AgentTarget,
    ClauseMatch,
    QueryClassification,
    QueryType,
    RoutePlan,
    TrustedRequestContext,
)
from agent.app.schemas.retrieval import RetrievalCandidate
from agent.app.tools.narrative_feature_extraction import NarrativeFeatureExtractionTool
from agent.app.tools.provenance import EvidencePackagingTool
from agent.app.tools.sql_retrieval import SqlRetrievalTool


class StubHybridTool:
    async def run(self, request):  # type: ignore[no-untyped-def]
        text = request.query_text.lower()
        if "rights" in text:
            doc_type = DocumentType.CONTRACT
            source = "10_licensing_contract.md#clause-14.3"
            snippet = "Matching rights apply to spin-off and sequel rights."
        elif "underserved audience" in text:
            doc_type = DocumentType.REPORT
            source = "07_strategic_fit_memo.md#heading-1"
            snippet = "Underserved international audiences and churn-heavy adults 25-45."
        elif "comparable titles" in text:
            doc_type = DocumentType.REPORT
            source = "08_comp_titles_notes.md#heading-1"
            snippet = (
                '"The Grid" has strong retention; avoid the slow pacing of '
                '"The Architect\'s Legacy".'
            )
        else:
            doc_type = DocumentType.SCRIPT
            source = "02_pilot_script.md#scene-10"
            snippet = (
                "The analog key mystery is a major hook, but technical jargon can be confusing."
            )
        return type(
            "StubResult",
            (),
            {
                "candidates": [
                    RetrievalCandidate(
                        document_id="doc-1",
                        section_id=source,
                        snippet=snippet,
                        source_reference=source,
                        retrieval_method=RetrievalMethod.HYBRID,
                        confidence_score=0.9,
                        document_type=doc_type,
                        claim_support_metadata={},
                    )
                ]
            },
        )()


class StubClauseTool:
    async def run(self, request):  # type: ignore[no-untyped-def]
        return type(
            "ClauseResult",
            (),
            {
                "clauses": [
                    ClauseMatch(
                        document_id="doc-1",
                        section_id="sec-1",
                        clause_text="Matching rights apply to spin-off and sequel rights.",
                        source_reference="10_licensing_contract.md#clause-14.3",
                    )
                ]
            },
        )()


def _context() -> AgentExecutionContext:
    return AgentExecutionContext(
        request=AgentRequest(
            message="Should we greenlight this original series?",
            context=TrustedRequestContext(user_id=1, session_id="session-1"),
        ),
        classification=QueryClassification(
            query_type=QueryType.ORIGINAL_EVAL,
            target_agents=[AgentTarget.NARRATIVE_ANALYSIS],
            reuse_cached_outputs=False,
            requires_recomputation=True,
        ),
        route_plan=RoutePlan(
            query_type=QueryType.ORIGINAL_EVAL,
            agent_sequence=[AgentTarget.NARRATIVE_ANALYSIS],
        ),
    )


@pytest.mark.asyncio
async def test_document_retrieval_agent_returns_ranked_packages() -> None:
    agent = DocumentRetrievalAgent(StubHybridTool(), EvidencePackagingTool())  # type: ignore[arg-type]
    result = await agent.run(_context())
    assert result.packages
    assert {package.focus for package in result.packages} == {
        RetrievalFocus.CREATIVE,
        RetrievalFocus.COMPARABLES,
        RetrievalFocus.CONTRACT,
        RetrievalFocus.STRATEGIC,
    }


@pytest.mark.asyncio
async def test_narrative_agent_returns_typed_story_outputs() -> None:
    retrieval = await DocumentRetrievalAgent(
        StubHybridTool(),  # type: ignore[arg-type]
        EvidencePackagingTool(),
    ).run(_context())
    agent = NarrativeAnalysisAgent(
        feature_tool=NarrativeFeatureExtractionTool(),
        provenance_tool=EvidencePackagingTool(),
    )
    result = await agent.run(_context(), retrieval)
    assert result.genre
    assert result.score_inputs.hook_strength > 0
    assert result.narrative_red_flags


@pytest.mark.asyncio
async def test_roi_agent_returns_scoring_inputs_and_comparable_evidence() -> None:
    retrieval = await DocumentRetrievalAgent(
        StubHybridTool(),  # type: ignore[arg-type]
        EvidencePackagingTool(),
    ).run(_context())
    narrative = await NarrativeAnalysisAgent(
        feature_tool=NarrativeFeatureExtractionTool(),
        provenance_tool=EvidencePackagingTool(),
    ).run(_context(), retrieval)
    result = await RoiPredictionAgent(SqlRetrievalTool(), EvidencePackagingTool()).run(
        _context(),
        retrieval,
        narrative,
    )
    assert result.completion_inputs.baseline_completion_rate > 0
    assert result.comparable_titles


@pytest.mark.asyncio
async def test_risk_agent_returns_typed_findings() -> None:
    retrieval = await DocumentRetrievalAgent(
        StubHybridTool(),  # type: ignore[arg-type]
        EvidencePackagingTool(),
    ).run(_context())
    agent = RiskContractAnalysisAgent(StubClauseTool(), EvidencePackagingTool())  # type: ignore[arg-type]
    result = await agent.run(_context(), retrieval)
    assert any(finding.risk_type == "matching_rights_constraint" for finding in result.findings)
    assert any(finding.severity_input == RiskSeverity.BLOCKER for finding in result.findings)


@pytest.mark.asyncio
async def test_catalog_fit_agent_returns_structured_inputs() -> None:
    retrieval = await DocumentRetrievalAgent(
        StubHybridTool(),  # type: ignore[arg-type]
        EvidencePackagingTool(),
    ).run(_context())
    agent = CatalogFitAgent(StubHybridTool(), EvidencePackagingTool())  # type: ignore[arg-type]
    result = await agent.run(_context(), retrieval)
    assert result.inputs.underserved_segments
