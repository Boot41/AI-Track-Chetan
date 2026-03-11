from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

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
    AgentRequest,
    AgentTarget,
    CachedOutputName,
    ComparisonOption,
    ComparisonState,
    EvidencePackagingRequest,
    QueryType,
    SessionAgentOutput,
    SessionState,
    SqlRetrievalRequest,
    TrustedRequestContext,
)
from agent.app.schemas.retrieval import RetrievalCandidate
from agent.app.tools.narrative_feature_extraction import NarrativeFeatureExtractionTool
from agent.app.tools.provenance import EvidencePackagingTool
from agent.app.tools.sql_retrieval import SqlRetrievalTool

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
def dummy_session_factory():  # type: ignore[no-untyped-def]
    return object()


def _cached_output(summary: str) -> SessionAgentOutput:
    return SessionAgentOutput(summary=summary, confidence=0.8, generated_at=datetime.now(UTC))


def test_query_classifier_matches_followup_fixtures() -> None:
    classifier = QueryClassifier()
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    for fixture in fixtures:
        classification = classifier.classify(fixture["query"])
        assert classification.query_type.value == fixture["expected_classification"]["query_type"]
        assert [target.value for target in classification.target_agents] == fixture["expected_classification"][
            "target_agents"
        ]


def test_query_classifier_uses_session_context_for_ambiguous_followup() -> None:
    classifier = QueryClassifier()
    classification = classifier.classify(
        "Why is that the case?",
        SessionState(query_type=QueryType.ACQUISITION_EVAL),
    )
    assert classification.query_type == QueryType.FOLLOWUP_WHY_RISK


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


def test_session_state_reuse_decision_prefers_cached_followup_outputs(dummy_session_factory) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    route = orchestrator.build_route_plan(
        QueryType.FOLLOWUP_WHY_ROI,
        SessionState(roi_output=_cached_output("Cached ROI output")),
    )
    assert route.cached_outputs_to_use == [CachedOutputName.ROI]
    assert route.outputs_to_recompute == []


@pytest.mark.asyncio
async def test_tool_interfaces_validate_typed_payloads() -> None:
    sql_result = await SqlRetrievalTool().run(
        SqlRetrievalRequest(pitch_id="pitch_shadow_protocol", metric_keys=["budget_assumption"])
    )
    assert sql_result.records[0].metric_key == "budget_assumption"

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
        {"query_text": "Why could this work?", "sections": [candidate.model_dump(mode="json")]}
    )
    assert features.features


def test_orchestrator_helper_logic_tracks_active_option_and_session_updates(dummy_session_factory) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    session_state = SessionState(
        comparison_state=ComparisonState(
            option_a=ComparisonOption(option_id="option-a", label="Neon Shore", query_type=QueryType.ORIGINAL_EVAL),
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


def test_typed_subagent_interfaces_are_explicit(dummy_session_factory) -> None:
    orchestrator = AgentOrchestrator(dummy_session_factory)
    assert isinstance(orchestrator._document_agent, DocumentRetrievalAgent)
    assert isinstance(orchestrator._narrative_agent, NarrativeAnalysisAgent)
    assert isinstance(orchestrator._roi_agent, RoiPredictionAgent)
    assert isinstance(orchestrator._risk_agent, RiskContractAnalysisAgent)
    assert isinstance(orchestrator._catalog_agent, CatalogFitAgent)


def test_backend_routing_glue_matches_agent_routing_spec() -> None:
    from app.schemas.contracts import AgentTarget as BackendAgentTarget
    from app.schemas.contracts import QueryType as BackendQueryType
    from app.agent.routing_spec import ROUTING_SPEC

    assert ROUTING_SPEC[BackendQueryType.ORIGINAL_EVAL].target_agents == [
        BackendAgentTarget.NARRATIVE_ANALYSIS,
        BackendAgentTarget.ROI_PREDICTION,
        BackendAgentTarget.RISK_CONTRACT_ANALYSIS,
        BackendAgentTarget.CATALOG_FIT,
        BackendAgentTarget.RECOMMENDATION_ENGINE,
    ]
