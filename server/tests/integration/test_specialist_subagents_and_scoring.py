from __future__ import annotations

from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.ingestion.service import DocumentIngestionService
from agent.app.schemas.orchestration import AgentRequest, SessionState, TrustedRequestContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_orchestrator_runs_retrieval_specialists_and_scorers_for_original_eval(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)

    result = await orchestrator.orchestrate(
        AgentRequest(
            message="Should we greenlight Shadow Protocol as an original series?",
            context=TrustedRequestContext(user_id=1, session_id="session-1"),
            session_state=SessionState(pitch_id="pitch_shadow_protocol"),
        )
    )

    assert result.retrieval_output is not None
    assert result.narrative_output is not None
    assert result.roi_output is not None
    assert result.risk_output is not None
    assert result.catalog_output is not None
    assert result.completion_score is not None
    assert result.roi_score is not None
    assert result.catalog_fit_score is not None
    assert result.recommendation_result is not None
    assert result.narrative_output.genre == "cyber-noir thriller"
    assert any(
        flag.flag == "technical_jargon_confusion"
        for flag in result.narrative_output.narrative_red_flags
    )
    assert any(
        title.title in {"The Grid", "comparable-signal"}
        for title in result.roi_output.comparable_titles
    )


async def test_orchestrator_surfaces_known_contract_and_catalog_signals_for_acquisition_eval(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)

    result = await orchestrator.orchestrate(
        AgentRequest(
            message="Should we acquire the Red Harbor Collection?",
            context=TrustedRequestContext(user_id=1, session_id="session-2"),
            session_state=SessionState(pitch_id="pitch_red_harbor"),
        )
    )

    assert result.risk_output is not None
    assert result.catalog_output is not None
    assert any(
        finding.risk_type == "exclusivity_window_overlap" for finding in result.risk_output.findings
    )
    assert any(
        finding.risk_type == "matching_rights_constraint" for finding in result.risk_output.findings
    )
    assert result.catalog_output.inputs.underserved_segments
    assert result.catalog_output.inputs.localization_implications
    assert result.recommendation_result is not None


async def test_recommendation_is_stable_for_identical_inputs(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)
    request = AgentRequest(
        message="Should we greenlight Shadow Protocol as an original series?",
        context=TrustedRequestContext(user_id=1, session_id="session-3"),
        session_state=SessionState(pitch_id="pitch_shadow_protocol"),
    )

    first = await orchestrator.orchestrate(request)
    second = await orchestrator.orchestrate(request)

    assert first.recommendation_result is not None
    assert second.recommendation_result is not None
    assert first.recommendation_result.outcome == second.recommendation_result.outcome
    assert first.recommendation_result.weighted_score == second.recommendation_result.weighted_score


async def test_followup_reuses_cached_subagent_payloads(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)
    initial = await orchestrator.orchestrate(
        AgentRequest(
            message="Should we greenlight Shadow Protocol as an original series?",
            context=TrustedRequestContext(user_id=1, session_id="session-4"),
            session_state=SessionState(pitch_id="pitch_shadow_protocol"),
        )
    )
    session_state = orchestrator.update_session_state(
        SessionState(pitch_id="pitch_shadow_protocol"),
        initial,
    )

    followup = await orchestrator.orchestrate(
        AgentRequest(
            message="Why is the narrative strong?",
            context=TrustedRequestContext(user_id=1, session_id="session-4"),
            session_state=session_state,
        )
    )

    assert any(item.cached for item in followup.invoked_agents)
    assert followup.narrative_output is not None
