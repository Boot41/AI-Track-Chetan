from __future__ import annotations

from google.adk.agents import Agent

from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.agents.query_classifier import QueryClassifier
from agent.app.agents.routing import ROUTING_MATRIX
from agent.app.formatters import format_public_response
from agent.app.persistence.session import get_sessionmaker
from agent.app.schemas.orchestration import (
    AgentRequest,
    AgentTarget,
    ClauseExtractionRequest,
    EvidencePackagingRequest,
    HybridDocumentRetrievalRequest,
    NarrativeFeatureExtractionRequest,
    QueryType,
    SessionState,
    SqlRetrievalRequest,
    TrustedRequestContext,
)
from agent.app.tools import (
    ClauseExtractionTool,
    EvidencePackagingTool,
    HybridDocumentRetrievalTool,
    NarrativeFeatureExtractionTool,
    SqlRetrievalTool,
)


def _infer_pitch_id_from_message(text: str) -> str | None:
    normalized = text.strip().lower()
    if "shadow protocol" in normalized:
        return "pitch_shadow_protocol"
    if "red harbor" in normalized:
        return "pitch_red_harbor"
    return None


async def orchestrate_query(
    message: str,
    user_id: int = 1,
    session_id: str = "session",
    pitch_id: str | None = None,
) -> dict[str, object]:
    resolved_pitch_id = pitch_id or _infer_pitch_id_from_message(message)
    orchestrator = AgentOrchestrator(get_sessionmaker())
    result = await orchestrator.orchestrate(
        AgentRequest(
            message=message,
            context=TrustedRequestContext(user_id=user_id, session_id=session_id),
            session_state=(
                SessionState(pitch_id=resolved_pitch_id)
                if resolved_pitch_id is not None
                else None
            ),
        )
    )
    return format_public_response(result)


def classify_query_for_delegation(
    message: str,
    pitch_id: str | None = None,
) -> dict[str, object]:
    classifier = QueryClassifier()
    classification = classifier.classify(message)
    route = ROUTING_MATRIX[classification.query_type]
    resolved_pitch_id = pitch_id or _infer_pitch_id_from_message(message)
    target_to_subagent = {
        AgentTarget.DOCUMENT_RETRIEVAL: "document_retrieval_agent",
        AgentTarget.NARRATIVE_ANALYSIS: "narrative_analysis_agent",
        AgentTarget.ROI_PREDICTION: "roi_prediction_agent",
        AgentTarget.RISK_CONTRACT_ANALYSIS: "risk_contract_analysis_agent",
        AgentTarget.CATALOG_FIT: "catalog_fit_agent",
    }
    recommended_subagents: list[str] = []
    for target in route.target_agents:
        subagent = target_to_subagent.get(target)
        if subagent and subagent not in recommended_subagents:
            recommended_subagents.append(subagent)
    if (
        "document_retrieval_agent" not in recommended_subagents
        and classification.query_type != QueryType.SCENARIO_CHANGE_BUDGET
    ):
        recommended_subagents.insert(0, "document_retrieval_agent")
    return {
        "query_type": classification.query_type.value,
        "target_agents": [target.value for target in classification.target_agents],
        "recommended_subagents": recommended_subagents,
        "inferred_pitch_id": resolved_pitch_id,
    }


async def hybrid_document_retrieval(
    query_text: str,
    pitch_id: str | None = None,
    limit: int = 5,
) -> dict[str, object]:
    resolved_pitch_id = pitch_id or _infer_pitch_id_from_message(query_text)
    tool = HybridDocumentRetrievalTool(get_sessionmaker())
    response = await tool.run(
        HybridDocumentRetrievalRequest(
            query_text=query_text,
            content_ids=[resolved_pitch_id] if resolved_pitch_id else [],
            limit=max(1, min(limit, 25)),
        )
    )
    return {
        "count": len(response.candidates),
        "candidates": [
            {
                "document_id": item.document_id,
                "section_id": item.section_id,
                "source_reference": item.source_reference,
                "confidence_score": item.confidence_score,
                "snippet": item.snippet,
            }
            for item in response.candidates
        ],
    }


async def narrative_feature_extraction(
    query_text: str,
    pitch_id: str | None = None,
    limit: int = 5,
) -> dict[str, object]:
    resolved_pitch_id = pitch_id or _infer_pitch_id_from_message(query_text)
    retrieval = HybridDocumentRetrievalTool(get_sessionmaker())
    retrieval_result = await retrieval.run(
        HybridDocumentRetrievalRequest(
            query_text=f"{query_text} narrative character arc tone pacing",
            content_ids=[resolved_pitch_id] if resolved_pitch_id else [],
            limit=max(1, min(limit, 25)),
        )
    )
    feature_tool = NarrativeFeatureExtractionTool()
    features = await feature_tool.run(
        NarrativeFeatureExtractionRequest(
            query_text=query_text,
            sections=retrieval_result.candidates,
        )
    )
    return {
        "summary": features.summary,
        "feature_count": len(features.features),
        "features": [
            {
                "name": feature.name,
                "value": feature.value,
                "confidence": feature.confidence,
                "rationale": feature.rationale,
            }
            for feature in features.features
        ],
    }


async def sql_retrieval(
    pitch_id: str | None = None,
    metric_keys: list[str] | None = None,
    active_option_id: str | None = None,
    message_hint: str | None = None,
) -> dict[str, object]:
    resolved_pitch_id = pitch_id or (
        _infer_pitch_id_from_message(message_hint) if message_hint else None
    )
    tool = SqlRetrievalTool()
    requested_keys = metric_keys or [
        "baseline_completion_rate",
        "comparable_completion_rate",
        "baseline_retention_lift",
        "projected_viewers",
        "projected_revenue",
        "total_cost",
        "retention_value",
        "franchise_value",
    ]
    response = await tool.run(
        SqlRetrievalRequest(
            pitch_id=resolved_pitch_id,
            metric_keys=requested_keys,
            active_option_id=active_option_id,
        )
    )
    return {
        "records": [
            {
                "metric_key": record.metric_key,
                "value": record.value,
                "source_table": record.source_table,
                "source_reference": record.source_reference,
            }
            for record in response.records
        ],
        "warnings": response.warnings,
    }


async def clause_extraction(
    query_text: str = "rights exclusivity territory matching rights localization",
    pitch_id: str | None = None,
    limit: int = 8,
) -> dict[str, object]:
    resolved_pitch_id = pitch_id or _infer_pitch_id_from_message(query_text)
    tool = ClauseExtractionTool(get_sessionmaker())
    response = await tool.run(
        ClauseExtractionRequest(
            query_text=query_text,
            content_ids=[resolved_pitch_id] if resolved_pitch_id else [],
            limit=max(1, min(limit, 25)),
        )
    )
    return {
        "count": len(response.clauses),
        "clauses": [
            {
                "document_id": item.document_id,
                "section_id": item.section_id,
                "source_reference": item.source_reference,
                "clause_text": item.clause_text,
                "risk_summary": item.risk_summary,
                "fact_value": item.fact_value,
            }
            for item in response.clauses
        ],
    }


async def evidence_packaging(
    query_text: str,
    claim_it_supports: str,
    used_by_agent: str = "document_retrieval",
    pitch_id: str | None = None,
    limit: int = 5,
) -> dict[str, object]:
    resolved_pitch_id = pitch_id or _infer_pitch_id_from_message(query_text)
    retrieval = HybridDocumentRetrievalTool(get_sessionmaker())
    retrieval_result = await retrieval.run(
        HybridDocumentRetrievalRequest(
            query_text=query_text,
            content_ids=[resolved_pitch_id] if resolved_pitch_id else [],
            limit=max(1, min(limit, 25)),
        )
    )
    agent_target_map = {
        "document_retrieval": AgentTarget.DOCUMENT_RETRIEVAL,
        "narrative_analysis": AgentTarget.NARRATIVE_ANALYSIS,
        "roi_prediction": AgentTarget.ROI_PREDICTION,
        "risk_contract_analysis": AgentTarget.RISK_CONTRACT_ANALYSIS,
        "catalog_fit": AgentTarget.CATALOG_FIT,
    }
    target = agent_target_map.get(used_by_agent, AgentTarget.DOCUMENT_RETRIEVAL)
    tool = EvidencePackagingTool()
    response = await tool.run(
        EvidencePackagingRequest(
            used_by_agent=target,
            claim_it_supports=claim_it_supports,
            retrieval_candidates=retrieval_result.candidates,
        )
    )
    return {
        "count": len(response.evidence),
        "evidence": [
            {
                "source_reference": item.source_reference,
                "snippet": item.snippet,
                "retrieval_method": item.retrieval_method.value,
                "confidence_score": item.confidence_score,
                "claim_it_supports": item.claim_it_supports,
                "used_by_agent": item.used_by_agent.value,
            }
            for item in response.evidence
        ],
    }


document_retrieval_agent = Agent(
    name="document_retrieval_agent",
    model="gemini-2.5-flash",
    description="Retrieves relevant document sections and packages evidence.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Call `hybrid_document_retrieval` first. Call `evidence_packaging` if needed. "
        "Then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[hybrid_document_retrieval, evidence_packaging],
    disallow_transfer_to_peers=True,
)


narrative_analysis_agent = Agent(
    name="narrative_analysis_agent",
    model="gemini-2.5-flash",
    description="Extracts narrative features from creative materials.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `narrative_feature_extraction`, then transfer control back to "
        "`streamlogic_orchestrator`."
    ),
    tools=[narrative_feature_extraction],
    disallow_transfer_to_peers=True,
)


roi_prediction_agent = Agent(
    name="roi_prediction_agent",
    model="gemini-2.5-flash",
    description="Retrieves structured metrics for completion, retention, and ROI.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `sql_retrieval`, then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[sql_retrieval],
    disallow_transfer_to_peers=True,
)


risk_contract_analysis_agent = Agent(
    name="risk_contract_analysis_agent",
    model="gemini-2.5-flash",
    description="Extracts and analyzes contract clauses and rights risk.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `clause_extraction`, then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[clause_extraction],
    disallow_transfer_to_peers=True,
)


catalog_fit_agent = Agent(
    name="catalog_fit_agent",
    model="gemini-2.5-flash",
    description="Retrieves strategic and comparable evidence for catalog fit signals.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `hybrid_document_retrieval` and optionally `evidence_packaging`, then transfer "
        "control back to `streamlogic_orchestrator`."
    ),
    tools=[hybrid_document_retrieval, evidence_packaging],
    disallow_transfer_to_peers=True,
)


final_response_agent = Agent(
    name="final_response_agent",
    model="gemini-2.5-flash",
    description="Generates the final stable response envelope via orchestrator.",
    instruction=(
        "Use `orchestrate_query` to generate the final structured response for the user message."
    ),
    tools=[orchestrate_query],
    disallow_transfer_to_peers=True,
)


root_agent = Agent(
    name="streamlogic_orchestrator",
    model="gemini-2.5-flash",
    description="Orchestration shell for StreamLogic AI.",
    instruction=(
        "Always call `classify_query_for_delegation` first. Transfer only to subagents listed in "
        "`recommended_subagents`, at most once each, and do not transfer to any other specialist. "
        "After specialist handoffs, call `orchestrate_query` directly to produce the final output. "
        "Do not answer directly and do not fabricate recommendation outputs."
    ),
    tools=[classify_query_for_delegation, orchestrate_query],
    sub_agents=[
        document_retrieval_agent,
        narrative_analysis_agent,
        roi_prediction_agent,
        risk_contract_analysis_agent,
        catalog_fit_agent,
    ],
)


async def run_orchestrator(
    orchestrator: AgentOrchestrator,
    message: str,
    user_id: int = 1,
    session_id: str = "session",
) -> dict[str, object]:
    result = await orchestrator.orchestrate(
        AgentRequest(
            message=message,
            context=TrustedRequestContext(user_id=user_id, session_id=session_id),
        )
    )
    return format_public_response(result)
