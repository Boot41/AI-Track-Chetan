from __future__ import annotations

from datetime import UTC, datetime
from logging import getLogger
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.app.agents.interfaces import (
    CatalogFitAgentInterface,
    DocumentRetrievalAgentInterface,
    NarrativeAnalysisAgentInterface,
    RiskContractAnalysisAgentInterface,
    RoiPredictionAgentInterface,
)
from agent.app.agents.query_classifier import QueryClassifier
from agent.app.agents.routing import ROUTING_MATRIX
from agent.app.agents.subagents import (
    CatalogFitAgent,
    DocumentRetrievalAgent,
    NarrativeAnalysisAgent,
    RiskContractAnalysisAgent,
    RoiPredictionAgent,
)
from agent.app.scorers import (
    CatalogFitScorer,
    CompletionRateScorer,
    RecommendationEngine,
    RiskSeverityScorer,
    RoiScorer,
)
from agent.app.schemas.orchestration import (
    AgentExecutionContext,
    AgentInvocation,
    AgentRequest,
    AgentTarget,
    CachedOutputName,
    CatalogAgentOutput,
    ComparisonOption,
    HandoffOutput,
    NarrativeAgentOutput,
    OrchestrationResult,
    QueryType,
    RetrievalAgentOutput,
    RiskAgentOutput,
    RoiAgentOutput,
    RoutePlan,
    SessionAgentOutput,
    SessionState,
    ToolInvocation,
    ToolName,
)
from agent.app.tools import (
    ClauseExtractionTool,
    EvidencePackagingTool,
    HybridDocumentRetrievalTool,
    NarrativeFeatureExtractionTool,
    SqlRetrievalTool,
)

logger = getLogger(__name__)


class AgentOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        classifier: QueryClassifier | None = None,
        document_agent: DocumentRetrievalAgentInterface | None = None,
        narrative_agent: NarrativeAnalysisAgentInterface | None = None,
        roi_agent: RoiPredictionAgentInterface | None = None,
        risk_agent: RiskContractAnalysisAgentInterface | None = None,
        catalog_agent: CatalogFitAgentInterface | None = None,
        completion_rate_scorer: CompletionRateScorer | None = None,
        roi_scorer: RoiScorer | None = None,
        risk_severity_scorer: RiskSeverityScorer | None = None,
        catalog_fit_scorer: CatalogFitScorer | None = None,
        recommendation_engine: RecommendationEngine | None = None,
    ) -> None:
        provenance_tool = EvidencePackagingTool()
        hybrid_tool = HybridDocumentRetrievalTool(session_factory)
        self._classifier = classifier or QueryClassifier()
        self._document_agent = document_agent or DocumentRetrievalAgent(
            hybrid_tool, provenance_tool
        )
        self._narrative_agent = narrative_agent or NarrativeAnalysisAgent(
            NarrativeFeatureExtractionTool(),
            provenance_tool,
        )
        self._roi_agent = roi_agent or RoiPredictionAgent(
            SqlRetrievalTool(), provenance_tool
        )
        self._risk_agent = risk_agent or RiskContractAnalysisAgent(
            ClauseExtractionTool(session_factory),
            provenance_tool,
        )
        self._catalog_agent = catalog_agent or CatalogFitAgent(
            hybrid_tool, provenance_tool
        )
        self._completion_rate_scorer = completion_rate_scorer or CompletionRateScorer()
        self._roi_scorer = roi_scorer or RoiScorer()
        self._risk_severity_scorer = risk_severity_scorer or RiskSeverityScorer()
        self._catalog_fit_scorer = catalog_fit_scorer or CatalogFitScorer()
        self._recommendation_engine = recommendation_engine or RecommendationEngine()

    async def orchestrate(self, request: AgentRequest) -> OrchestrationResult:
        request = AgentRequest.model_validate(request)
        session_state = request.session_state or SessionState()
        classification = self._classifier.classify(request.message, session_state)
        route_plan = self.build_route_plan(classification.query_type, session_state)
        context = AgentExecutionContext(
            request=request,
            classification=classification,
            route_plan=route_plan,
            active_option_id=route_plan.active_option_id,
            comparison_options=self._comparison_options(session_state),
        )

        logger.info("classifier_result=%s", classification.model_dump(mode="json"))
        logger.info("route_plan=%s", route_plan.model_dump(mode="json"))

        result = OrchestrationResult(
            classification=classification,
            route_plan=route_plan,
            active_option_id=route_plan.active_option_id,
            comparison_option_ids=[
                option.option_id for option in context.comparison_options
            ],
            recommendation_config=self._recommendation_engine.config,
        )

        if self._needs_document_prefetch(classification.query_type):
            result.retrieval_output = await self._document_agent.run(context)
            result.invoked_agents.append(
                AgentInvocation(
                    target=AgentTarget.DOCUMENT_RETRIEVAL,
                    details={"support_agent": True},
                )
            )
            result.invoked_tools.extend(
                [
                    ToolInvocation(tool_name=ToolName.HYBRID_DOCUMENT_RETRIEVAL),
                    ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                ]
            )

        for target in route_plan.agent_sequence:
            if target == AgentTarget.DOCUMENT_RETRIEVAL:
                if result.retrieval_output is None:
                    result.retrieval_output = await self._document_agent.run(context)
                result.invoked_agents.append(AgentInvocation(target=target))
                result.invoked_tools.extend(
                    [
                        ToolInvocation(tool_name=ToolName.HYBRID_DOCUMENT_RETRIEVAL),
                        ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                    ]
                )
            elif target == AgentTarget.NARRATIVE_ANALYSIS:
                cached = self._cached_output(
                    session_state,
                    CachedOutputName.NARRATIVE,
                    NarrativeAgentOutput,
                )
                if CachedOutputName.NARRATIVE in route_plan.cached_outputs_to_use and cached:
                    result.narrative_output = cached
                    session_output = session_state.narrative_output
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={
                                "summary": session_output.summary if session_output else cached.summary
                            },
                        )
                    )
                else:
                    result.narrative_output = await self._narrative_agent.run(
                        context, result.retrieval_output
                    )
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(
                                tool_name=ToolName.NARRATIVE_FEATURE_EXTRACTION
                            ),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target == AgentTarget.ROI_PREDICTION:
                cached = self._cached_output(
                    session_state,
                    CachedOutputName.ROI,
                    RoiAgentOutput,
                )
                if CachedOutputName.ROI in route_plan.cached_outputs_to_use and cached:
                    result.roi_output = cached
                    session_output = session_state.roi_output
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={
                                "summary": session_output.summary if session_output else cached.summary
                            },
                        )
                    )
                else:
                    narrative_context = result.narrative_output or self._cached_output(
                        session_state,
                        CachedOutputName.NARRATIVE,
                        NarrativeAgentOutput,
                    )
                    result.roi_output = await self._roi_agent.run(
                        context,
                        result.retrieval_output,
                        narrative_context,
                    )
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(tool_name=ToolName.SQL_RETRIEVAL),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target == AgentTarget.RISK_CONTRACT_ANALYSIS:
                cached = self._cached_output(
                    session_state,
                    CachedOutputName.RISK,
                    RiskAgentOutput,
                )
                if CachedOutputName.RISK in route_plan.cached_outputs_to_use and cached:
                    result.risk_output = cached
                    session_output = session_state.risk_output
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={
                                "summary": session_output.summary if session_output else cached.summary
                            },
                        )
                    )
                else:
                    result.risk_output = await self._risk_agent.run(
                        context, result.retrieval_output
                    )
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(tool_name=ToolName.CLAUSE_EXTRACTION),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target == AgentTarget.CATALOG_FIT:
                cached = self._cached_output(
                    session_state,
                    CachedOutputName.CATALOG,
                    CatalogAgentOutput,
                )
                if CachedOutputName.CATALOG in route_plan.cached_outputs_to_use and cached:
                    result.catalog_output = cached
                    session_output = session_state.catalog_output
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={
                                "summary": session_output.summary if session_output else cached.summary
                            },
                        )
                    )
                else:
                    result.catalog_output = await self._catalog_agent.run(
                        context, result.retrieval_output
                    )
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.append(
                        ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING)
                    )
            elif target == AgentTarget.COMPARISON_SYNTHESIS:
                dependencies = [
                    invocation.target
                    for invocation in result.invoked_agents
                    if invocation.target not in {AgentTarget.DOCUMENT_RETRIEVAL, target}
                ]
                summary = (
                    "Comparison synthesis is limited to the currently active option because "
                    "the Phase 3 scaffolding does not yet pass multiple option payloads."
                )
                result.handoffs.append(
                    HandoffOutput(
                        target=target,
                        summary=summary,
                        dependencies=dependencies,
                    )
                )
                result.invoked_agents.append(
                    AgentInvocation(target=target, details={"handoff_only": True})
                )
                if route_plan.evaluate_all_comparison_options and not context.comparison_options:
                    result.warnings.append(
                        "Comparison query received no option state; evaluated only the active evidence context."
                    )
            elif target == AgentTarget.RECOMMENDATION_ENGINE:
                narrative_output = result.narrative_output or self._cached_output(
                    session_state,
                    CachedOutputName.NARRATIVE,
                    NarrativeAgentOutput,
                )
                roi_output = result.roi_output or self._cached_output(
                    session_state,
                    CachedOutputName.ROI,
                    RoiAgentOutput,
                )
                risk_output = result.risk_output or self._cached_output(
                    session_state,
                    CachedOutputName.RISK,
                    RiskAgentOutput,
                )
                catalog_output = result.catalog_output or self._cached_output(
                    session_state,
                    CachedOutputName.CATALOG,
                    CatalogAgentOutput,
                )
                if (
                    roi_output is None
                    or risk_output is None
                    or catalog_output is None
                ):
                    result.warnings.append(
                        "Recommendation engine could not run because one or more specialist outputs were unavailable."
                    )
                    continue
                result.completion_score = self._completion_rate_scorer.score(
                    roi_output.completion_inputs
                )
                result.roi_score = self._roi_scorer.score(
                    roi_output.roi_inputs,
                    roi_output.retention_inputs,
                    roi_output.cost_per_view_inputs,
                    result.completion_score,
                )
                result.risk_score = self._risk_severity_scorer.score(
                    risk_output.findings
                )
                result.catalog_fit_score = self._catalog_fit_scorer.score(
                    catalog_output.inputs
                )
                result.recommendation_result = self._recommendation_engine.recommend(
                    narrative_output.score_inputs if narrative_output is not None else None,
                    result.roi_score,
                    result.risk_score,
                    result.catalog_fit_score,
                )
                result.invoked_agents.append(
                    AgentInvocation(
                        target=target,
                        details={
                            "recommendation": result.recommendation_result.outcome.value,
                            "weighted_score": result.recommendation_result.weighted_score,
                        },
                    )
                )

        result.warnings.extend(
            self._warnings_for_missing_outputs(session_state, route_plan)
        )
        logger.info(
            "orchestrator_summary=%s",
            {
                "subagents_invoked": [
                    item.target.value for item in result.invoked_agents
                ],
                "tools_invoked": [
                    item.tool_name.value for item in result.invoked_tools
                ],
                "cache_reuse": [
                    item.target.value for item in result.invoked_agents if item.cached
                ],
                "recomputed": [item.value for item in route_plan.outputs_to_recompute],
                "recommendation": (
                    result.recommendation_result.outcome.value
                    if result.recommendation_result is not None
                    else None
                ),
            },
        )
        return result

    def build_route_plan(
        self, query_type: QueryType, session_state: SessionState | None
    ) -> RoutePlan:
        session_state = session_state or SessionState()
        route = ROUTING_MATRIX[query_type]
        cached_outputs_to_use = [
            output_name
            for output_name in route.reusable_outputs
            if self._session_output(session_state, output_name) is not None
        ]
        outputs_to_recompute = list(route.recompute_outputs)
        if (
            query_type == QueryType.FOLLOWUP_WHY_NARRATIVE
            and session_state.narrative_output is not None
        ):
            outputs_to_recompute = []
        if (
            query_type == QueryType.FOLLOWUP_WHY_ROI
            and session_state.roi_output is not None
        ):
            outputs_to_recompute = []
        if (
            query_type == QueryType.FOLLOWUP_WHY_RISK
            and session_state.risk_output is not None
        ):
            outputs_to_recompute = []
        if (
            query_type == QueryType.FOLLOWUP_WHY_CATALOG
            and session_state.catalog_output is not None
        ):
            outputs_to_recompute = []

        return RoutePlan(
            query_type=query_type,
            agent_sequence=route.target_agents,
            cached_outputs_to_use=cached_outputs_to_use,
            outputs_to_recompute=outputs_to_recompute,
            active_option_id=self.resolve_active_option(query_type, session_state),
            evaluate_all_comparison_options=query_type == QueryType.COMPARISON,
            support_agents=[AgentTarget.DOCUMENT_RETRIEVAL]
            if self._needs_document_prefetch(query_type)
            else [],
        )

    def resolve_active_option(
        self, query_type: QueryType, session_state: SessionState | None
    ) -> str | None:
        if session_state is None or session_state.comparison_state is None:
            return None
        if query_type == QueryType.COMPARISON:
            return session_state.comparison_state.active_option
        return (
            session_state.active_option or session_state.comparison_state.active_option
        )

    def update_session_state(
        self, state: SessionState | None, result: OrchestrationResult
    ) -> SessionState:
        current = state or SessionState()
        now = datetime.now(UTC)
        retrieval_context = list(current.retrieval_context)
        retrieval_context.extend(
            candidate.section_id
            for candidate in (
                result.retrieval_output.raw_candidates
                if result.retrieval_output is not None
                else []
            )
        )
        return current.model_copy(
            update={
                "query_type": result.classification.query_type,
                "narrative_output": self._to_session_output(
                    result.narrative_output, now
                )
                or current.narrative_output,
                "roi_output": self._to_session_output(result.roi_output, now)
                or current.roi_output,
                "risk_output": self._to_session_output(result.risk_output, now)
                or current.risk_output,
                "catalog_output": self._to_session_output(result.catalog_output, now)
                or current.catalog_output,
                "active_option": result.active_option_id,
                "retrieval_context": retrieval_context,
            }
        )

    def _comparison_options(
        self, session_state: SessionState
    ) -> list[ComparisonOption]:
        if session_state.comparison_state is None:
            return []
        return [
            session_state.comparison_state.option_a,
            session_state.comparison_state.option_b,
        ]

    def _needs_document_prefetch(self, query_type: QueryType) -> bool:
        return query_type != QueryType.SCENARIO_CHANGE_BUDGET

    def _session_output(
        self,
        session_state: SessionState,
        output_name: CachedOutputName,
    ) -> SessionAgentOutput | None:
        output_map = {
            CachedOutputName.NARRATIVE: session_state.narrative_output,
            CachedOutputName.ROI: session_state.roi_output,
            CachedOutputName.RISK: session_state.risk_output,
            CachedOutputName.CATALOG: session_state.catalog_output,
        }
        return output_map[output_name]

    def _cached_output(
        self,
        session_state: SessionState,
        output_name: CachedOutputName,
        schema: type[Any],
    ) -> Any | None:
        session_output = self._session_output(session_state, output_name)
        if session_output is None or not session_output.payload:
            return None
        return schema.model_validate(session_output.payload)

    def _warnings_for_missing_outputs(
        self,
        session_state: SessionState,
        route_plan: RoutePlan,
    ) -> list[str]:
        warnings: list[str] = []
        for output_name in route_plan.cached_outputs_to_use:
            if self._session_output(session_state, output_name) is None:
                warnings.append(
                    f"Requested cached output {output_name.value} was unavailable."
                )
        return warnings

    def _to_session_output(
        self, value: object, generated_at: datetime
    ) -> SessionAgentOutput | None:
        if value is None or not hasattr(value, "summary"):
            return None
        summary = getattr(value, "summary")
        if not isinstance(summary, str):
            return None
        confidence = getattr(value, "confidence", 0.75)
        if not isinstance(confidence, (int, float)):
            confidence = 0.75
        payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else {}
        return SessionAgentOutput(
            summary=summary,
            confidence=float(confidence),
            generated_at=generated_at,
            payload=payload,
        )
