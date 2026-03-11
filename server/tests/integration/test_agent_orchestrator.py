from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from agent.app.agents.interfaces import (
    CatalogFitAgentInterface,
    DocumentRetrievalAgentInterface,
    NarrativeAnalysisAgentInterface,
    RiskContractAnalysisAgentInterface,
    RoiPredictionAgentInterface,
)
from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.schemas.ingestion import RetrievalMethod
from agent.app.schemas.orchestration import (
    AgentExecutionContext,
    AgentRequest,
    AgentTarget,
    CatalogAgentOutput,
    ComparisonOption,
    ComparisonState,
    EvidenceReference,
    NarrativeAgentOutput,
    QueryType,
    RetrievalAgentOutput,
    RiskAgentOutput,
    RoiAgentOutput,
    SessionAgentOutput,
    SessionState,
    TrustedRequestContext,
)
from agent.app.schemas.retrieval import RetrievalCandidate
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _request(message: str, session_state: SessionState | None = None) -> AgentRequest:
    return AgentRequest(
        message=message,
        context=TrustedRequestContext(user_id=1, session_id="session-1"),
        session_state=session_state,
    )


def _session_output(summary: str) -> SessionAgentOutput:
    return SessionAgentOutput(summary=summary, confidence=0.9, generated_at=datetime.now(UTC))


@pytest.fixture
def dummy_session_factory() -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], object())


class FakeDocumentAgent(DocumentRetrievalAgentInterface):
    async def run(self, context: AgentExecutionContext) -> RetrievalAgentOutput:
        candidate = RetrievalCandidate(
            document_id="doc-1",
            section_id="section-1",
            snippet="Market memo cites a gap in young adult thrillers.",
            source_reference="07_strategic_fit_memo.md#section-1",
            retrieval_method=RetrievalMethod.HYBRID,
            confidence_score=0.88,
            document_type="report",
            claim_support_metadata={"matched_methods": ["fts", "vector"]},
        )
        return RetrievalAgentOutput(
            summary="Retrieved support sections.",
            raw_candidates=[candidate],
            evidence=[
                EvidenceReference(
                    document_id="doc-1",
                    section_id="section-1",
                    snippet=candidate.snippet,
                    source_reference=candidate.source_reference,
                    retrieval_method=RetrievalMethod.HYBRID,
                    confidence_score=0.88,
                    used_by_agent=AgentTarget.DOCUMENT_RETRIEVAL,
                    claim_it_supports="retrieval",
                )
            ],
        )


class FakeNarrativeAgent(NarrativeAnalysisAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> NarrativeAgentOutput:
        return NarrativeAgentOutput(summary="Narrative output", features=[], evidence=[])


class FakeRoiAgent(RoiPredictionAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
        narrative_output: NarrativeAgentOutput | None,
    ) -> RoiAgentOutput:
        return RoiAgentOutput(
            summary="ROI output", assumptions=["budget stable"], metrics=[], evidence=[]
        )


class FakeRiskAgent(RiskContractAnalysisAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> RiskAgentOutput:
        return RiskAgentOutput(summary="Risk output", clauses=[], evidence=[])


class FakeCatalogAgent(CatalogFitAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> CatalogAgentOutput:
        return CatalogAgentOutput(summary="Catalog output", signals=["gap"], evidence=[])


async def test_query_type_maps_to_expected_subagents(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(
        dummy_session_factory,
        document_agent=FakeDocumentAgent(),
        narrative_agent=FakeNarrativeAgent(),
        roi_agent=FakeRoiAgent(),
        risk_agent=FakeRiskAgent(),
        catalog_agent=FakeCatalogAgent(),
    )

    result = await orchestrator.orchestrate(_request("Should we greenlight this original series?"))
    assert [item.target.value for item in result.invoked_agents] == [
        "document_retrieval",
        "narrative_analysis",
        "roi_prediction",
        "risk_contract_analysis",
        "catalog_fit",
        "recommendation_engine",
    ]


async def test_followup_routing_reuses_cached_outputs(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(
        dummy_session_factory,
        document_agent=FakeDocumentAgent(),
        narrative_agent=FakeNarrativeAgent(),
        roi_agent=FakeRoiAgent(),
        risk_agent=FakeRiskAgent(),
        catalog_agent=FakeCatalogAgent(),
    )
    state = SessionState(roi_output=_session_output("cached roi"))

    result = await orchestrator.orchestrate(_request("Why is the ROI low?", state))
    assert result.classification.query_type == QueryType.FOLLOWUP_WHY_ROI
    assert [item.target.value for item in result.invoked_agents if item.cached] == [
        "roi_prediction"
    ]


async def test_scenario_change_routing_recomputes_downstream_dependencies(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(
        dummy_session_factory,
        document_agent=FakeDocumentAgent(),
        narrative_agent=FakeNarrativeAgent(),
        roi_agent=FakeRoiAgent(),
        risk_agent=FakeRiskAgent(),
        catalog_agent=FakeCatalogAgent(),
    )
    state = SessionState(
        narrative_output=_session_output("cached narrative"),
        risk_output=_session_output("cached risk"),
        catalog_output=_session_output("cached catalog"),
    )

    result = await orchestrator.orchestrate(
        _request("What if we add Hindi dubbing and Bahasa subtitles?", state)
    )
    assert result.classification.query_type == QueryType.SCENARIO_CHANGE_LOCALIZATION
    assert result.route_plan.outputs_to_recompute
    assert [handoff.target.value for handoff in result.handoffs] == ["recommendation_engine"]


async def test_comparison_targeting_preserves_active_option(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(
        dummy_session_factory,
        document_agent=FakeDocumentAgent(),
        narrative_agent=FakeNarrativeAgent(),
        roi_agent=FakeRoiAgent(),
        risk_agent=FakeRiskAgent(),
        catalog_agent=FakeCatalogAgent(),
    )
    state = SessionState(
        comparison_state=ComparisonState(
            option_a=ComparisonOption(
                option_id="option-a", label="Neon Shore", query_type=QueryType.ORIGINAL_EVAL
            ),
            option_b=ComparisonOption(
                option_id="option-b",
                label="Red Harbor Catalog",
                query_type=QueryType.ACQUISITION_EVAL,
            ),
            active_option="option-b",
        ),
        active_option="option-b",
        catalog_output=_session_output("cached catalog"),
    )

    result = await orchestrator.orchestrate(
        _request("Why does option B fit our catalog better?", state)
    )
    assert result.active_option_id == "option-b"
    assert result.classification.query_type == QueryType.FOLLOWUP_WHY_CATALOG


async def test_orchestrator_uses_mocked_subagents_and_updates_session_state(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(
        dummy_session_factory,
        document_agent=FakeDocumentAgent(),
        narrative_agent=FakeNarrativeAgent(),
        roi_agent=FakeRoiAgent(),
        risk_agent=FakeRiskAgent(),
        catalog_agent=FakeCatalogAgent(),
    )

    result = await orchestrator.orchestrate(_request("Should we acquire this catalog?"))
    state = orchestrator.update_session_state(SessionState(), result)

    assert result.classification.query_type == QueryType.ACQUISITION_EVAL
    assert state.roi_output is not None
    assert state.catalog_output is not None
    assert state.query_type == QueryType.ACQUISITION_EVAL


async def test_orchestrator_recomputes_when_followup_cache_missing(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(
        dummy_session_factory,
        document_agent=FakeDocumentAgent(),
        narrative_agent=FakeNarrativeAgent(),
        roi_agent=FakeRoiAgent(),
        risk_agent=FakeRiskAgent(),
        catalog_agent=FakeCatalogAgent(),
    )

    result = await orchestrator.orchestrate(_request("Why is the contract risk high?"))
    assert result.classification.query_type == QueryType.FOLLOWUP_WHY_RISK
    assert [item.target.value for item in result.invoked_agents if item.cached] == []
    assert any(item.target.value == "risk_contract_analysis" for item in result.invoked_agents)
