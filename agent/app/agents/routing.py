from __future__ import annotations

from app.schemas.orchestration import (
    AgentTarget,
    CachedOutputName,
    QueryType,
    RouteDefinition,
)

ROUTING_MATRIX: dict[QueryType, RouteDefinition] = {
    QueryType.ORIGINAL_EVAL: RouteDefinition(
        query_type=QueryType.ORIGINAL_EVAL,
        target_agents=[
            AgentTarget.NARRATIVE_ANALYSIS,
            AgentTarget.ROI_PREDICTION,
            AgentTarget.RISK_CONTRACT_ANALYSIS,
            AgentTarget.CATALOG_FIT,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        recompute_outputs=[
            CachedOutputName.NARRATIVE,
            CachedOutputName.ROI,
            CachedOutputName.RISK,
            CachedOutputName.CATALOG,
        ],
        downstream_handoffs=[AgentTarget.RECOMMENDATION_ENGINE],
    ),
    QueryType.ACQUISITION_EVAL: RouteDefinition(
        query_type=QueryType.ACQUISITION_EVAL,
        target_agents=[
            AgentTarget.RISK_CONTRACT_ANALYSIS,
            AgentTarget.CATALOG_FIT,
            AgentTarget.ROI_PREDICTION,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        recompute_outputs=[
            CachedOutputName.RISK,
            CachedOutputName.CATALOG,
            CachedOutputName.ROI,
        ],
        downstream_handoffs=[AgentTarget.RECOMMENDATION_ENGINE],
    ),
    QueryType.COMPARISON: RouteDefinition(
        query_type=QueryType.COMPARISON,
        target_agents=[
            AgentTarget.NARRATIVE_ANALYSIS,
            AgentTarget.ROI_PREDICTION,
            AgentTarget.RISK_CONTRACT_ANALYSIS,
            AgentTarget.CATALOG_FIT,
            AgentTarget.COMPARISON_SYNTHESIS,
        ],
        recompute_outputs=[
            CachedOutputName.NARRATIVE,
            CachedOutputName.ROI,
            CachedOutputName.RISK,
            CachedOutputName.CATALOG,
        ],
        comparison_enabled=True,
        downstream_handoffs=[AgentTarget.COMPARISON_SYNTHESIS],
    ),
    QueryType.FOLLOWUP_WHY_NARRATIVE: RouteDefinition(
        query_type=QueryType.FOLLOWUP_WHY_NARRATIVE,
        target_agents=[AgentTarget.NARRATIVE_ANALYSIS],
        reusable_outputs=[CachedOutputName.NARRATIVE],
        recompute_outputs=[CachedOutputName.NARRATIVE],
    ),
    QueryType.FOLLOWUP_WHY_ROI: RouteDefinition(
        query_type=QueryType.FOLLOWUP_WHY_ROI,
        target_agents=[AgentTarget.ROI_PREDICTION],
        reusable_outputs=[CachedOutputName.ROI],
        recompute_outputs=[CachedOutputName.ROI],
    ),
    QueryType.FOLLOWUP_WHY_RISK: RouteDefinition(
        query_type=QueryType.FOLLOWUP_WHY_RISK,
        target_agents=[AgentTarget.RISK_CONTRACT_ANALYSIS],
        reusable_outputs=[CachedOutputName.RISK],
        recompute_outputs=[CachedOutputName.RISK],
    ),
    QueryType.FOLLOWUP_WHY_CATALOG: RouteDefinition(
        query_type=QueryType.FOLLOWUP_WHY_CATALOG,
        target_agents=[AgentTarget.CATALOG_FIT],
        reusable_outputs=[CachedOutputName.CATALOG],
        recompute_outputs=[CachedOutputName.CATALOG],
    ),
    QueryType.SCENARIO_CHANGE_BUDGET: RouteDefinition(
        query_type=QueryType.SCENARIO_CHANGE_BUDGET,
        target_agents=[AgentTarget.ROI_PREDICTION, AgentTarget.RECOMMENDATION_ENGINE],
        reusable_outputs=[
            CachedOutputName.NARRATIVE,
            CachedOutputName.RISK,
            CachedOutputName.CATALOG,
        ],
        recompute_outputs=[CachedOutputName.ROI],
        downstream_handoffs=[AgentTarget.RECOMMENDATION_ENGINE],
    ),
    QueryType.SCENARIO_CHANGE_LOCALIZATION: RouteDefinition(
        query_type=QueryType.SCENARIO_CHANGE_LOCALIZATION,
        target_agents=[
            AgentTarget.ROI_PREDICTION,
            AgentTarget.CATALOG_FIT,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        reusable_outputs=[CachedOutputName.NARRATIVE, CachedOutputName.RISK],
        recompute_outputs=[CachedOutputName.ROI, CachedOutputName.CATALOG],
        downstream_handoffs=[AgentTarget.RECOMMENDATION_ENGINE],
    ),
    QueryType.GENERAL_QUESTION: RouteDefinition(
        query_type=QueryType.GENERAL_QUESTION,
        target_agents=[AgentTarget.DOCUMENT_RETRIEVAL],
    ),
}
