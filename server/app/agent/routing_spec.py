from __future__ import annotations

from app.schemas.contracts import AgentTarget, QueryClassification, QueryType

ROUTING_SPEC: dict[QueryType, QueryClassification] = {
    QueryType.ORIGINAL_EVAL: QueryClassification(
        query_type=QueryType.ORIGINAL_EVAL,
        target_agents=[
            AgentTarget.NARRATIVE_ANALYSIS,
            AgentTarget.ROI_PREDICTION,
            AgentTarget.RISK_CONTRACT_ANALYSIS,
            AgentTarget.CATALOG_FIT,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        reuse_cached_outputs=False,
        requires_recomputation=True,
    ),
    QueryType.ACQUISITION_EVAL: QueryClassification(
        query_type=QueryType.ACQUISITION_EVAL,
        target_agents=[
            AgentTarget.RISK_CONTRACT_ANALYSIS,
            AgentTarget.CATALOG_FIT,
            AgentTarget.ROI_PREDICTION,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        reuse_cached_outputs=False,
        requires_recomputation=True,
    ),
    QueryType.COMPARISON: QueryClassification(
        query_type=QueryType.COMPARISON,
        target_agents=[
            AgentTarget.NARRATIVE_ANALYSIS,
            AgentTarget.ROI_PREDICTION,
            AgentTarget.RISK_CONTRACT_ANALYSIS,
            AgentTarget.CATALOG_FIT,
            AgentTarget.COMPARISON_SYNTHESIS,
        ],
        reuse_cached_outputs=False,
        requires_recomputation=True,
    ),
    QueryType.FOLLOWUP_WHY_NARRATIVE: QueryClassification(
        query_type=QueryType.FOLLOWUP_WHY_NARRATIVE,
        target_agents=[AgentTarget.NARRATIVE_ANALYSIS],
        reuse_cached_outputs=True,
        requires_recomputation=False,
    ),
    QueryType.FOLLOWUP_WHY_ROI: QueryClassification(
        query_type=QueryType.FOLLOWUP_WHY_ROI,
        target_agents=[AgentTarget.ROI_PREDICTION],
        reuse_cached_outputs=True,
        requires_recomputation=False,
    ),
    QueryType.FOLLOWUP_WHY_RISK: QueryClassification(
        query_type=QueryType.FOLLOWUP_WHY_RISK,
        target_agents=[AgentTarget.RISK_CONTRACT_ANALYSIS],
        reuse_cached_outputs=True,
        requires_recomputation=False,
    ),
    QueryType.FOLLOWUP_WHY_CATALOG: QueryClassification(
        query_type=QueryType.FOLLOWUP_WHY_CATALOG,
        target_agents=[AgentTarget.CATALOG_FIT],
        reuse_cached_outputs=True,
        requires_recomputation=False,
    ),
    QueryType.SCENARIO_CHANGE_BUDGET: QueryClassification(
        query_type=QueryType.SCENARIO_CHANGE_BUDGET,
        target_agents=[AgentTarget.ROI_PREDICTION, AgentTarget.RECOMMENDATION_ENGINE],
        reuse_cached_outputs=True,
        requires_recomputation=True,
    ),
    QueryType.SCENARIO_CHANGE_LOCALIZATION: QueryClassification(
        query_type=QueryType.SCENARIO_CHANGE_LOCALIZATION,
        target_agents=[
            AgentTarget.ROI_PREDICTION,
            AgentTarget.CATALOG_FIT,
            AgentTarget.RECOMMENDATION_ENGINE,
        ],
        reuse_cached_outputs=True,
        requires_recomputation=True,
    ),
    QueryType.GENERAL_QUESTION: QueryClassification(
        query_type=QueryType.GENERAL_QUESTION,
        target_agents=[AgentTarget.DOCUMENT_RETRIEVAL],
        reuse_cached_outputs=False,
        requires_recomputation=False,
    ),
}
