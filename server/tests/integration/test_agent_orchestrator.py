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
from agent.app.schemas.evaluation import (
    CatalogFitInputs,
    CatalogFitSignal,
    CharacterArcSignal,
    ComparableTitleEvidence,
    CompletionRateInputs,
    CostPerViewInputs,
    FranchiseAssessment,
    NarrativeScoreInputs,
    RetentionLiftInputs,
    RetrievalEvidencePackage,
    RetrievalFocus,
    RetrievalSourceReference,
    RiskFinding,
    RiskSeverity,
    RoiInputs,
)
from agent.app.schemas.ingestion import DocumentType, RetrievalMethod
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
    SqlMetricRecord,
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


def _candidate() -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id="doc-1",
        section_id="section-1",
        snippet="Market memo cites a gap in young adult thrillers and strong retention hooks.",
        source_reference="07_strategic_fit_memo.md#section-1",
        retrieval_method=RetrievalMethod.HYBRID,
        confidence_score=0.88,
        document_type=DocumentType.REPORT,
        claim_support_metadata={"matched_methods": ["fts", "vector"]},
    )


def _source_ref() -> RetrievalSourceReference:
    candidate = _candidate()
    return RetrievalSourceReference(
        document_id=candidate.document_id,
        section_id=candidate.section_id,
        source_reference=candidate.source_reference,
        retrieval_method=candidate.retrieval_method,
        confidence_score=candidate.confidence_score,
    )


def _narrative_output() -> NarrativeAgentOutput:
    return NarrativeAgentOutput(
        summary="Narrative output",
        features=[],
        genre="thriller",
        themes=["identity"],
        tone=["paranoid", "fast-paced"],
        pacing="binge-forward",
        character_arcs=[
            CharacterArcSignal(
                character_name="Elara Vance",
                arc_summary="Analyst to insurgent",
                confidence=0.8,
                source_references=[_source_ref()],
            )
        ],
        franchise_potential=FranchiseAssessment(
            level="high",
            confidence=0.8,
            rationale="Spin-off support is explicit.",
            source_references=[_source_ref()],
        ),
        narrative_red_flags=[],
        score_inputs=NarrativeScoreInputs(
            hook_strength=0.85,
            pacing_strength=0.8,
            character_strength=0.78,
            franchise_strength=0.8,
            red_flag_penalty=0.05,
        ),
        evidence=[],
    )


def _roi_output() -> RoiAgentOutput:
    return RoiAgentOutput(
        summary="ROI output",
        assumptions=["budget stable"],
        metrics=[
            SqlMetricRecord(
                metric_key="baseline_completion_rate",
                value=0.66,
                source_table="structured_metrics_seed",
                source_reference="metrics:pitch_shadow_protocol",
            )
        ],
        completion_inputs=CompletionRateInputs(
            baseline_completion_rate=0.66,
            comparable_completion_rate=0.71,
            hook_strength=0.84,
            bingeability=0.8,
            pacing_penalty=0.08,
            narrative_clarity_penalty=0.05,
        ),
        retention_inputs=RetentionLiftInputs(
            baseline_retention_lift=0.04,
            audience_alignment=0.82,
            churn_reduction_signal=0.76,
            franchise_uplift=0.78,
            regional_demand_signal=0.74,
        ),
        roi_inputs=RoiInputs(
            total_cost=62000000.0,
            projected_viewers=17000000.0,
            projected_revenue=148000000.0,
            retention_value=15000000.0,
            franchise_value=12000000.0,
        ),
        cost_per_view_inputs=CostPerViewInputs(
            total_cost=62000000.0,
            projected_viewers=17000000.0,
        ),
        comparable_titles=[
            ComparableTitleEvidence(
                title="The Grid",
                rationale="Comparable high-concept cyber thriller with strong retention.",
                source_references=[_source_ref()],
            )
        ],
        evidence=[],
    )


def _risk_output() -> RiskAgentOutput:
    return RiskAgentOutput(
        summary="Risk output",
        clauses=[],
        findings=[
            RiskFinding(
                risk_type="territory_carve_out",
                severity_input=RiskSeverity.MEDIUM,
                rationale="Territory restrictions exist.",
                remediation_hint="Model the excluded territory separately.",
                source_references=[_source_ref()],
            )
        ],
        evidence=[],
    )


def _catalog_output() -> CatalogAgentOutput:
    return CatalogAgentOutput(
        summary="Catalog output",
        signals=["gap"],
        inputs=CatalogFitInputs(
            underserved_segments=[
                CatalogFitSignal(
                    signal="underserved_segment_alignment",
                    strength=0.84,
                    rationale="Fills a known segment gap.",
                    source_references=[_source_ref()],
                )
            ],
            churn_demographics=[],
            genre_gaps=[],
            regional_demand=[],
            competitor_overlap=[],
            strategic_timing=[],
            localization_implications=[],
        ),
        evidence=[],
    )


def _session_output(summary: str, payload: dict[str, object]) -> SessionAgentOutput:
    return SessionAgentOutput(
        summary=summary,
        confidence=0.9,
        generated_at=datetime.now(UTC),
        payload=payload,
    )


@pytest.fixture
def dummy_session_factory() -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], object())


class FakeDocumentAgent(DocumentRetrievalAgentInterface):
    async def run(self, context: AgentExecutionContext) -> RetrievalAgentOutput:
        candidate = _candidate()
        return RetrievalAgentOutput(
            summary="Retrieved support sections.",
            raw_candidates=[candidate],
            packages=[
                RetrievalEvidencePackage(
                    focus=RetrievalFocus.CREATIVE,
                    query_text="creative",
                    summary="creative evidence",
                    source_references=[_source_ref()],
                ),
                RetrievalEvidencePackage(
                    focus=RetrievalFocus.COMPARABLES,
                    query_text="comparables",
                    summary="comparable evidence",
                    source_references=[_source_ref()],
                ),
                RetrievalEvidencePackage(
                    focus=RetrievalFocus.CONTRACT,
                    query_text="contract",
                    summary="contract evidence",
                    source_references=[_source_ref()],
                ),
                RetrievalEvidencePackage(
                    focus=RetrievalFocus.STRATEGIC,
                    query_text="strategic",
                    summary="strategic evidence",
                    source_references=[_source_ref()],
                ),
            ],
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
        return _narrative_output()


class FakeRoiAgent(RoiPredictionAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
        narrative_output: NarrativeAgentOutput | None,
    ) -> RoiAgentOutput:
        return _roi_output()


class FakeRiskAgent(RiskContractAnalysisAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> RiskAgentOutput:
        return _risk_output()


class FakeCatalogAgent(CatalogFitAgentInterface):
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> CatalogAgentOutput:
        return _catalog_output()


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
    assert result.recommendation_result is not None
    assert result.roi_score is not None


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
    roi_output = _roi_output()
    state = SessionState(
        roi_output=_session_output("cached roi", roi_output.model_dump(mode="json"))
    )

    result = await orchestrator.orchestrate(_request("Why is the ROI low?", state))
    assert result.classification.query_type == QueryType.FOLLOWUP_WHY_ROI
    assert [item.target.value for item in result.invoked_agents if item.cached] == [
        "roi_prediction"
    ]
    assert result.roi_output is not None


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
        narrative_output=_session_output(
            "cached narrative", _narrative_output().model_dump(mode="json")
        ),
        risk_output=_session_output("cached risk", _risk_output().model_dump(mode="json")),
        catalog_output=_session_output("cached catalog", _catalog_output().model_dump(mode="json")),
    )

    result = await orchestrator.orchestrate(
        _request("What if we add Hindi dubbing and Bahasa subtitles?", state)
    )
    assert result.classification.query_type == QueryType.SCENARIO_CHANGE_LOCALIZATION
    assert result.route_plan.outputs_to_recompute
    assert result.recommendation_result is not None


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
        catalog_output=_session_output("cached catalog", _catalog_output().model_dump(mode="json")),
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
    assert state.roi_output.payload["summary"] == "ROI output"
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
