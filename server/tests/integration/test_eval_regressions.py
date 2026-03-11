from __future__ import annotations

from datetime import UTC, datetime

from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.formatters import format_public_response
from agent.app.ingestion.service import DocumentIngestionService
from agent.app.operations import OperationalDataWorkflow
from agent.app.schemas.orchestration import AgentRequest, SessionState, TrustedRequestContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.contracts import PublicResponseContract


def _request(
    message: str,
    *,
    session_id: str,
    pitch_id: str | None = None,
    session_state: SessionState | None = None,
) -> AgentRequest:
    state = session_state or SessionState(pitch_id=pitch_id)
    if state.pitch_id is None and pitch_id is not None:
        state = state.model_copy(update={"pitch_id": pitch_id})
    return AgentRequest(
        message=message,
        context=TrustedRequestContext(user_id=1, session_id=session_id),
        session_state=state,
    )


async def test_eval_suite_original_and_acquisition_queries_are_grounded_and_stable(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)

    original = await orchestrator.orchestrate(
        _request(
            "Should we greenlight Shadow Protocol as an original series?",
            session_id="eval-original",
            pitch_id="pitch_shadow_protocol",
        )
    )
    acquisition = await orchestrator.orchestrate(
        _request(
            "Should we acquire the Red Harbor Collection?",
            session_id="eval-acquisition",
            pitch_id="pitch_red_harbor",
        )
    )

    assert original.retrieval_output is not None
    assert original.retrieval_output.raw_candidates
    assert original.recommendation_result is not None
    assert original.roi_output is not None
    assert original.roi_output.comparable_titles
    assert acquisition.risk_output is not None
    assert any(
        f.risk_type == "matching_rights_constraint" for f in acquisition.risk_output.findings
    )
    assert any(
        f.risk_type == "exclusivity_window_overlap" for f in acquisition.risk_output.findings
    )
    assert acquisition.recommendation_result is not None

    repeat = await orchestrator.orchestrate(
        _request(
            "Should we greenlight Shadow Protocol as an original series?",
            session_id="eval-original-repeat",
            pitch_id="pitch_shadow_protocol",
        )
    )
    assert repeat.recommendation_result is not None
    assert repeat.recommendation_result.outcome == original.recommendation_result.outcome
    assert (
        repeat.recommendation_result.weighted_score == original.recommendation_result.weighted_score
    )


async def test_eval_suite_followup_and_comparison_paths_are_explicit(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)

    initial = await orchestrator.orchestrate(
        _request(
            "Should we greenlight Shadow Protocol as an original series?",
            session_id="eval-followup",
            pitch_id="pitch_shadow_protocol",
        )
    )
    state = orchestrator.update_session_state(
        SessionState(pitch_id="pitch_shadow_protocol"),
        initial,
    )
    followup = await orchestrator.orchestrate(
        _request(
            "Why is the ROI strong?",
            session_id="eval-followup",
            session_state=state,
        )
    )
    assert any(item.cached for item in followup.invoked_agents)
    assert followup.classification.query_type.value == "followup_why_roi"

    weak_comparison = await orchestrator.orchestrate(
        _request(
            "Compare these options for me.",
            session_id="eval-comparison-weak",
            pitch_id="pitch_shadow_protocol",
        )
    )
    assert weak_comparison.classification.query_type.value == "comparison"
    assert any(
        "Comparison context is incomplete" in warning for warning in weak_comparison.warnings
    )


async def test_eval_suite_public_contract_schema_stability(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)
    result = await orchestrator.orchestrate(
        _request(
            "Should we acquire the Red Harbor Collection?",
            session_id="eval-contract-shape",
            pitch_id="pitch_red_harbor",
        )
    )
    public_payload = format_public_response(result)
    contract = PublicResponseContract.model_validate(public_payload)

    assert set(public_payload) == {"answer", "scorecard", "evidence", "meta"}
    assert set(contract.meta.model_dump()) == {"warnings", "confidence", "review_required"}
    assert contract.scorecard.query_type.value == "acquisition_eval"
    assert all(item.source_reference for item in contract.evidence)


async def test_eval_suite_handles_low_confidence_when_no_documents_are_indexed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestrator = AgentOrchestrator(session_factory)
    result = await orchestrator.orchestrate(
        _request(
            "Should we greenlight this original series?",
            session_id="eval-empty-index",
            pitch_id="pitch_shadow_protocol",
        )
    )
    public_payload = format_public_response(result)
    contract = PublicResponseContract.model_validate(public_payload)

    assert contract.meta.review_required is True
    assert any("No supporting evidence" in warning for warning in contract.meta.warnings)


async def test_eval_suite_cache_is_invalidated_when_index_fingerprint_changes(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    orchestrator = AgentOrchestrator(session_factory)
    initial = await orchestrator.orchestrate(
        _request(
            "Should we greenlight Shadow Protocol as an original series?",
            session_id="eval-cache-invalidation",
            pitch_id="pitch_shadow_protocol",
        )
    )
    state = orchestrator.update_session_state(
        SessionState(pitch_id="pitch_shadow_protocol"),
        initial,
    )
    stale_state = state.model_copy(
        update={
            "retrieval_context": [
                entry
                for entry in state.retrieval_context
                if not entry.startswith("index_fingerprint:")
            ]
            + ["index_fingerprint:stale-fingerprint"],
        }
    )
    result = await orchestrator.orchestrate(
        _request(
            "Why is the narrative score low?",
            session_id="eval-cache-invalidation",
            session_state=stale_state,
        )
    )

    assert any("cache was invalidated" in warning.lower() for warning in result.warnings)
    assert not any(invocation.cached for invocation in result.invoked_agents)


async def test_operational_workflow_reports_competitor_catalog_and_index_state(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await DocumentIngestionService().ingest_corpus(db)
    workflow = OperationalDataWorkflow(session_factory)
    index_state = await workflow.corpus_index_state()
    competitor_state = await workflow.competitor_catalog_state()
    source_fingerprint = workflow.source_fingerprint()

    assert index_state.document_count > 0
    assert len(index_state.fingerprint) == 16
    assert source_fingerprint
    assert competitor_state.source_count >= 1
    if competitor_state.refreshed_at is not None:
        assert competitor_state.refreshed_at <= datetime.now(UTC).replace(tzinfo=None)
