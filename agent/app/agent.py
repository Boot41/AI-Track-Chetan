from __future__ import annotations

import re
from typing import Any
from google.adk.agents import Agent

from .agents.orchestrator import AgentOrchestrator
from .agents.query_classifier import QueryClassifier
from .agents.routing import ROUTING_MATRIX
from .config import get_settings
from .formatters import format_public_response
from .persistence.session import get_sessionmaker
from .schemas.orchestration import (
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
from .tools import (
    ClauseExtractionTool,
    EvidencePackagingTool,
    HybridDocumentRetrievalTool,
    NarrativeFeatureExtractionTool,
    SqlRetrievalTool,
)

AGENT_MODEL = get_settings().agent_model


def _infer_pitch_ids_from_message(text: str | None) -> list[str]:
    if not text:
        return []
    normalized = text.strip().lower()
    ids = []
    if "shadow protocol" in normalized or "shadow_protocol" in normalized or "shadowprotocol" in normalized:
        ids.append("pitch_shadow_protocol")
    if "red harbor" in normalized or "red_harbor" in normalized or "redharbor" in normalized:
        ids.append("pitch_red_harbor")
    
    # Check for direct pitch_id patterns
    for match in re.findall(r"pitch_[a-z0-9_]+", normalized):
        if match not in ids:
            ids.append(match)
    return ids


def _infer_pitch_id_from_message(text: str | None) -> str | None:
    ids = _infer_pitch_ids_from_message(text)
    return ids[0] if ids else None


async def orchestrate_query(
    message: str,
    user_id: int = 1,
    session_id: str = "session",
    pitch_id: str | None = None,
    tool_context: Any | None = None,
) -> dict[str, object]:
    # Try to get session state from tool_context if passed by ADK
    session_state_payload = None
    if tool_context and hasattr(tool_context, "state"):
        session_state_payload = tool_context.state.get("session_state_payload")
    
    # Resolve and normalize pitch IDs
    pitch_ids = _infer_pitch_ids_from_message(pitch_id) or _infer_pitch_ids_from_message(message)
    resolved_pitch_id = pitch_ids[0] if pitch_ids else None
    
    orchestrator = AgentOrchestrator(get_sessionmaker())
    
    state = None
    if session_state_payload:
        from .schemas.orchestration import SessionState as OrchestratorSessionState
        state = OrchestratorSessionState.model_validate(session_state_payload)
        # Ensure the pitch_id is set if inferred from message or passed as arg
        if not state.pitch_id and resolved_pitch_id:
            state.pitch_id = resolved_pitch_id
    elif resolved_pitch_id is not None:
        state = SessionState(pitch_id=resolved_pitch_id)

    result = await orchestrator.orchestrate(
        AgentRequest(
            message=message,
            context=TrustedRequestContext(user_id=user_id, session_id=session_id),
            session_state=state,
        )
    )

    response = format_public_response(result)

    # Add a machine-readable summary of ALL evidence for the LLM to see
    evidence_summary: list[str] = []
    evidence_items_raw = response.get("evidence")
    evidence_items = (
        [item for item in evidence_items_raw if isinstance(item, dict)]
        if isinstance(evidence_items_raw, list)
        else []
    )
    for item in evidence_items:
        ref = item.get("source_reference", "unknown")
        snippet_value = item.get("snippet", "")
        snippet = snippet_value[:200] if isinstance(snippet_value, str) else ""
        agent = item.get("used_by_agent", "unknown")
        evidence_summary.append(f"[{ref}] (via {agent}): {snippet}")

    # Add a clear summary of metrics for the LLM
    scorecard_raw = response.get("scorecard")
    scorecard = scorecard_raw if isinstance(scorecard_raw, dict) else {}
    metrics_summary = (
        f"OFFICIAL METRICS for {resolved_pitch_id or 'request'}:\n"
        f"- Recommendation: {scorecard.get('recommendation')}\n"
        f"- Narrative Score: {scorecard.get('narrative_score')}\n"
        f"- Projected ROI: {scorecard.get('estimated_roi')}\n"
        f"- Completion Rate: {scorecard.get('projected_completion_rate')}\n"
        f"- Risk Level: {scorecard.get('risk_level')}\n"
        f"- Catalog Fit: {scorecard.get('catalog_fit_score')}\n"
    )

    # We include this in a field that the LLM will see
    response["llm_context"] = {
        "metrics": metrics_summary,
        "evidence": "\n".join(evidence_summary[:20]),
        "pitch_id_used": resolved_pitch_id,
        "all_pitch_ids_detected": pitch_ids,
        "query_type": response.get("query_type")
    }
    
    return response


def classify_query_for_delegation(
    message: str,
    pitch_id: str | None = None,
    tool_context: Any | None = None,
) -> dict[str, object]:
    # Try to get session state from tool_context
    session_state_payload = None
    if tool_context and hasattr(tool_context, "state"):
        session_state_payload = tool_context.state.get("session_state_payload")
    
    state = None
    if session_state_payload:
        from .schemas.orchestration import SessionState as OrchestratorSessionState
        state = OrchestratorSessionState.model_validate(session_state_payload)

    classifier = QueryClassifier()
    classification = classifier.classify(message, state)
    
    # Override classification to COMPARISON if multiple pitch IDs are detected
    pitch_ids = _infer_pitch_ids_from_message(pitch_id) or (([state.pitch_id] if state.pitch_id else []) if state else []) or _infer_pitch_ids_from_message(message)
    if len(pitch_ids) >= 2 and classification.query_type != QueryType.COMPARISON:
        classification.query_type = QueryType.COMPARISON
        # Update target agents for comparison
        route = ROUTING_MATRIX[QueryType.COMPARISON]
        classification.target_agents = route.target_agents

    route = ROUTING_MATRIX[classification.query_type]
    resolved_pitch_id = pitch_ids[0] if pitch_ids else None
    
    target_to_subagent = {
        AgentTarget.DOCUMENT_RETRIEVAL: "document_retrieval_agent",
        AgentTarget.NARRATIVE_ANALYSIS: "narrative_analysis_agent",
        AgentTarget.ROI_PREDICTION: "roi_prediction_agent",
        AgentTarget.RISK_CONTRACT_ANALYSIS: "risk_contract_analysis_agent",
        AgentTarget.CATALOG_FIT: "catalog_fit_agent",
        AgentTarget.COMPARISON_SYNTHESIS: "final_response_agent", # Handle comparison in final synthesis
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
        "pitch_id": resolved_pitch_id,
        "inferred_pitch_id": resolved_pitch_id,
        "all_detected_pitch_ids": pitch_ids,
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
    tool = SqlRetrievalTool(get_sessionmaker())
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
    model=AGENT_MODEL,
    description="Retrieves relevant document sections and packages evidence.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Call `hybrid_document_retrieval` first (ALWAYS pass the `pitch_id` provided by the orchestrator). "
        "Call `evidence_packaging` if needed (pass the `pitch_id`). "
        "Then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[hybrid_document_retrieval, evidence_packaging],
    disallow_transfer_to_peers=True,
)


narrative_analysis_agent = Agent(
    name="narrative_analysis_agent",
    model=AGENT_MODEL,
    description="Extracts narrative features from creative materials.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `hybrid_document_retrieval` to collect relevant scenes/sections (ALWAYS pass the `pitch_id`), "
        "then `narrative_feature_extraction` for narrative signals (pass the `pitch_id`), and "
        "`evidence_packaging` for traceable citations (pass the `pitch_id`). "
        "Then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[hybrid_document_retrieval, narrative_feature_extraction, evidence_packaging],
    disallow_transfer_to_peers=True,
)


roi_prediction_agent = Agent(
    name="roi_prediction_agent",
    model=AGENT_MODEL,
    description="Retrieves structured metrics for completion, retention, and ROI.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `sql_retrieval` for structured business metrics (ALWAYS pass the `pitch_id`), "
        "optionally `hybrid_document_retrieval` for contextual evidence (pass the `pitch_id`), and "
        "`evidence_packaging` for traceable citations (pass the `pitch_id`). "
        "Then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[sql_retrieval, hybrid_document_retrieval, evidence_packaging],
    disallow_transfer_to_peers=True,
)


risk_contract_analysis_agent = Agent(
    name="risk_contract_analysis_agent",
    model=AGENT_MODEL,
    description="Extracts and analyzes contract clauses and rights risk.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `clause_extraction` for contractual risk clauses (ALWAYS pass the `pitch_id`), "
        "optionally `hybrid_document_retrieval` for supporting document context (pass the `pitch_id`), and "
        "`evidence_packaging` for traceable citations (pass the `pitch_id`). "
        "Then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[clause_extraction, hybrid_document_retrieval, evidence_packaging],
    disallow_transfer_to_peers=True,
)


catalog_fit_agent = Agent(
    name="catalog_fit_agent",
    model=AGENT_MODEL,
    description="Retrieves strategic and comparable evidence for catalog fit signals.",
    instruction=(
        "Worker-only agent. Do not provide user-facing answers. "
        "Use `hybrid_document_retrieval` for catalog/market narrative evidence (ALWAYS pass the `pitch_id`), "
        "`sql_retrieval` for comparable platform metrics when relevant (pass the `pitch_id`), and "
        "`evidence_packaging` for traceable citations (pass the `pitch_id`). "
        "Then transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[hybrid_document_retrieval, sql_retrieval, evidence_packaging],
    disallow_transfer_to_peers=True,
)


final_response_agent = Agent(
    name="final_response_agent",
    model=AGENT_MODEL,
    description="Generates the final stable response envelope via orchestrator.",
    instruction=(
        "You are a response generator. Your ONLY task is to call the `orchestrate_query` tool "
        "with the user's message. DO NOT try to answer the user yourself. DO NOT synthesize any "
        "text before or after calling the tool. After calling `orchestrate_query`, you MUST "
        "immediately transfer control back to `streamlogic_orchestrator`."
    ),
    tools=[orchestrate_query],
    disallow_transfer_to_peers=True,
)


root_agent = Agent(
    name="streamlogic_orchestrator",
    model=AGENT_MODEL,
    description="Orchestration shell for StreamLogic AI.",
    instruction=(
        "You are the main orchestrator for StreamLogic AI. Your goal is to provide high-quality, "
        "evidence-backed decision support for OTT content investments.\n\n"
        "1. Always call `classify_query_for_delegation` first to understand the request, identify the target project (pitch_id), and get subagent recommendations.\n"
        "2. Transfer to the recommended subagents to gather specific analysis. ALWAYS pass the `pitch_id` you found in step 1 to these subagents.\n"
        "3. Transfer to `final_response_agent` to call `orchestrate_query` and generate the official "
        "structured scorecard, evidence items, and deterministic metrics required for platform stability. ALWAYS pass the `pitch_id` to `orchestrate_query`.\n"
        "4. Use the information from the subagents AND the `orchestrate_query` output to synthesize a "
        "thoughtful, professional, and nuanced final response. YOU MUST incorporate the official "
        "metrics (e.g., ROI, completion rates, catalog fit) from the `orchestrate_query` scorecard "
        "into your text response. Do not just repeat the tool's summary; provide your own "
        "analyst-level perspective on the subtext, nuances, and risks."
    ),
    tools=[classify_query_for_delegation],
    sub_agents=[
        document_retrieval_agent,
        narrative_analysis_agent,
        roi_prediction_agent,
        risk_contract_analysis_agent,
        catalog_fit_agent,
        final_response_agent,
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
