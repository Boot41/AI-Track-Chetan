from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.agents.query_classifier import QueryClassifier
from agent.app.agents.routing import ROUTING_MATRIX
from agent.app.agents.subagents import (
    CatalogFitAgent,
    DocumentRetrievalAgent,
    NarrativeAnalysisAgent,
    RiskContractAnalysisAgent,
    RoiPredictionAgent,
)
from agent.app.schemas.ingestion import DocumentType, RetrievalMethod
from agent.app.schemas.orchestration import (
    AgentTarget,
    CachedOutputName,
    ComparisonOption,
    ComparisonState,
    EvidencePackagingRequest,
    NarrativeFeatureExtractionRequest,
    QueryType,
    SessionAgentOutput,
    SessionState,
    SqlRetrievalRequest,
)
from agent.app.schemas.retrieval import RetrievalCandidate
from agent.app.tools.narrative_feature_extraction import NarrativeFeatureExtractionTool
from agent.app.tools.provenance import EvidencePackagingTool
from agent.app.tools.sql_retrieval import SqlRetrievalTool
from app.agent import (
    classify_query_for_delegation,
    final_response_agent,
    orchestrate_query,
    root_agent,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "agent"
    / "app"
    / "evals"
    / "fixtures"
    / "phase0"
    / "followup_routing_cases.json"
)


@pytest.fixture
def dummy_session_factory() -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], object())


def _cached_output(summary: str) -> SessionAgentOutput:
    return SessionAgentOutput(
        summary=summary,
        confidence=0.8,
        generated_at=datetime.now(UTC),
        payload={"summary": summary},
    )


def test_query_classifier_matches_followup_fixtures() -> None:
    classifier = QueryClassifier()
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    for fixture in fixtures:
        classification = classifier.classify(fixture["query"])
        assert classification.query_type.value == fixture["expected_classification"]["query_type"]
        assert [target.value for target in classification.target_agents] == fixture[
            "expected_classification"
        ]["target_agents"]


def test_query_classifier_uses_session_context_for_ambiguous_followup() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify(
        "Why is that the case?",
        SessionState(query_type=QueryType.ACQUISITION_EVAL),
    )
    assert classification.query_type == QueryType.FOLLOWUP_WHY_RISK


def test_query_classifier_prioritizes_original_eval_when_original_signals_are_explicit() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify(
        "Should we greenlight this original series for our catalog?"
    )
    assert classification.query_type == QueryType.ORIGINAL_EVAL


def test_query_classifier_marks_narrative_followup_for_recompute_when_cache_is_missing() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify("Why is the narrative score low?")
    assert classification.query_type == QueryType.FOLLOWUP_WHY_NARRATIVE
    assert classification.requires_recomputation is True


def test_query_classifier_routes_character_arc_prompts_to_narrative_followup() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify(
        "Describe the character arc for the protagonist in Shadow Protocol "
        "and cite evidence from the pilot script."
    )
    assert classification.query_type == QueryType.FOLLOWUP_WHY_NARRATIVE


def test_query_classifier_routes_ip_ownership_contract_query_to_acquisition_eval() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify(
        "Trace the IP ownership claim in Red Harbor back to the contract section."
    )
    assert classification.query_type == QueryType.ACQUISITION_EVAL


def test_query_classifier_routes_territory_roi_query_to_acquisition_eval() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify(
        "Assess Red Harbor territory restrictions impact on our global ROI model."
    )
    assert classification.query_type == QueryType.ACQUISITION_EVAL


def test_routing_matrix_encodes_documented_defaults() -> None:
    assert ROUTING_MATRIX[QueryType.ORIGINAL_EVAL].target_agents == [
        AgentTarget.NARRATIVE_ANALYSIS,
        AgentTarget.ROI_PREDICTION,
        AgentTarget.RISK_CONTRACT_ANALYSIS,
        AgentTarget.CATALOG_FIT,
        AgentTarget.RECOMMENDATION_ENGINE,
    ]
    assert ROUTING_MATRIX[QueryType.SCENARIO_CHANGE_LOCALIZATION].recompute_outputs == [
        CachedOutputName.ROI,
        CachedOutputName.CATALOG,
    ]
    assert ROUTING_MATRIX[QueryType.COMPARISON].comparison_enabled is True
    assert (
        ROUTING_MATRIX[QueryType.COMPARISON].target_agents[-1] == AgentTarget.COMPARISON_SYNTHESIS
    )


def test_session_state_reuse_decision_prefers_cached_followup_outputs(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    route = orchestrator.build_route_plan(
        QueryType.FOLLOWUP_WHY_ROI,
        SessionState(roi_output=_cached_output("Cached ROI output")),
    )
    assert route.cached_outputs_to_use == [CachedOutputName.ROI]
    assert route.outputs_to_recompute == []


def test_session_state_reuse_decision_clears_narrative_recompute_when_cache_exists(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    route = orchestrator.build_route_plan(
        QueryType.FOLLOWUP_WHY_NARRATIVE,
        SessionState(narrative_output=_cached_output("Cached narrative output")),
    )
    assert route.cached_outputs_to_use == [CachedOutputName.NARRATIVE]
    assert route.outputs_to_recompute == []


@pytest.mark.asyncio
async def test_tool_interfaces_validate_typed_payloads() -> None:
    sql_result = await SqlRetrievalTool().run(
        SqlRetrievalRequest(
            pitch_id="pitch_shadow_protocol",
            metric_keys=["baseline_completion_rate"],
        )
    )
    assert sql_result.records[0].metric_key == "baseline_completion_rate"

    candidate = RetrievalCandidate(
        document_id="doc-1",
        section_id="section-1",
        snippet="A thriller with a buried secret.",
        source_reference="02_pilot_script.md#scene-1",
        retrieval_method=RetrievalMethod.HYBRID,
        confidence_score=0.9,
        document_type=DocumentType.SCRIPT,
        claim_support_metadata={},
    )
    packaged = await EvidencePackagingTool().run(
        EvidencePackagingRequest(
            used_by_agent=AgentTarget.NARRATIVE_ANALYSIS,
            claim_it_supports="narrative analysis",
            retrieval_candidates=[candidate],
            sql_records=sql_result.records,
        )
    )
    assert len(packaged.evidence) == 2
    assert {item.retrieval_method.value for item in packaged.evidence} == {"hybrid", "sql"}

    features = await NarrativeFeatureExtractionTool().run(
        NarrativeFeatureExtractionRequest(
            query_text="Why could this work?",
            sections=[candidate],
        )
    )
    assert features.features


def test_orchestrator_helper_logic_tracks_active_option_and_session_updates(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    session_state = SessionState(
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
    )
    route = orchestrator.build_route_plan(QueryType.FOLLOWUP_WHY_CATALOG, session_state)
    assert route.active_option_id == "option-b"


def test_typed_subagent_interfaces_are_explicit(
    dummy_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    assert isinstance(orchestrator._document_agent, DocumentRetrievalAgent)
    assert isinstance(orchestrator._narrative_agent, NarrativeAnalysisAgent)
    assert isinstance(orchestrator._roi_agent, RoiPredictionAgent)
    assert isinstance(orchestrator._risk_agent, RiskContractAnalysisAgent)
    assert isinstance(orchestrator._catalog_agent, CatalogFitAgent)


def test_adk_final_response_agent_exposes_orchestrator_tool() -> None:
    assert final_response_agent.tools
    assert orchestrate_query in final_response_agent.tools
    assert final_response_agent.disallow_transfer_to_peers is True
    assert root_agent.tools
    assert classify_query_for_delegation in root_agent.tools
    assert orchestrate_query in root_agent.tools


def test_adk_root_agent_exposes_specialist_subagents() -> None:
    assert root_agent.sub_agents
    subagent_names = {agent.name for agent in root_agent.sub_agents}
    assert subagent_names == {
        "document_retrieval_agent",
        "narrative_analysis_agent",
        "roi_prediction_agent",
        "risk_contract_analysis_agent",
        "catalog_fit_agent",
    }
    for agent in root_agent.sub_agents:
        if agent.name != "final_response_agent":
            assert agent.disallow_transfer_to_peers is True


def test_delegation_classifier_returns_narrative_specialist_for_arc_prompt() -> None:
    payload = classify_query_for_delegation(
        "Analyze the narrative pacing of Shadow Protocol and mid-pilot drop-off risks."
    )
    assert payload["query_type"] == "followup_why_narrative"
    assert payload["recommended_subagents"] == [
        "document_retrieval_agent",
        "narrative_analysis_agent",
    ]


def test_delegation_classifier_infers_pitch_id_for_red_harbor() -> None:
    payload = classify_query_for_delegation(
        "Assess the impact of Red Harbor territory restrictions on global ROI."
    )
    assert payload["inferred_pitch_id"] == "pitch_red_harbor"


def test_backend_routing_glue_matches_agent_routing_spec() -> None:
    from app.agent.routing_spec import ROUTING_SPEC
    from app.schemas.contracts import AgentTarget as BackendAgentTarget
    from app.schemas.contracts import QueryType as BackendQueryType

    assert ROUTING_SPEC[BackendQueryType.ORIGINAL_EVAL].target_agents == [
        BackendAgentTarget.NARRATIVE_ANALYSIS,
        BackendAgentTarget.ROI_PREDICTION,
        BackendAgentTarget.RISK_CONTRACT_ANALYSIS,
        BackendAgentTarget.CATALOG_FIT,
        BackendAgentTarget.RECOMMENDATION_ENGINE,
    ]
