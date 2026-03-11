from __future__ import annotations

from datetime import UTC, datetime
from logging import getLogger

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.app.agents.query_classifier import QueryClassifier
from agent.app.agents.routing import ROUTING_MATRIX
from agent.app.agents.subagents import (
    CatalogFitAgent,
    DocumentRetrievalAgent,
    NarrativeAnalysisAgent,
    RiskContractAnalysisAgent,
    RoiPredictionAgent,
)
from agent.app.schemas.orchestration import (
    AgentExecutionContext,
    AgentInvocation,
    AgentRequest,
    AgentTarget,
    CachedOutputName,
    ComparisonOption,
    HandoffOutput,
    OrchestrationResult,
    QueryType,
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
        document_agent: DocumentRetrievalAgent | None = None,
        narrative_agent: NarrativeAnalysisAgent | None = None,
        roi_agent: RoiPredictionAgent | None = None,
        risk_agent: RiskContractAnalysisAgent | None = None,
        catalog_agent: CatalogFitAgent | None = None,
    ) -> None:
        provenance_tool = EvidencePackagingTool()
        hybrid_tool = HybridDocumentRetrievalTool(session_factory)
        self._classifier = classifier or QueryClassifier()
        self._document_agent = document_agent or DocumentRetrievalAgent(hybrid_tool, provenance_tool)
        self._narrative_agent = narrative_agent or NarrativeAnalysisAgent(
            NarrativeFeatureExtractionTool(),
            provenance_tool,
        )
        self._roi_agent = roi_agent or RoiPredictionAgent(SqlRetrievalTool(), provenance_tool)
        self._risk_agent = risk_agent or RiskContractAnalysisAgent(
            ClauseExtractionTool(session_factory),
            provenance_tool,
        )
        self._catalog_agent = catalog_agent or CatalogFitAgent(hybrid_tool, provenance_tool)

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
            comparison_option_ids=[option.option_id for option in context.comparison_options],
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
                if CachedOutputName.NARRATIVE in route_plan.cached_outputs_to_use and session_state.narrative_output:
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={"summary": session_state.narrative_output.summary},
                        )
                    )
                else:
                    result.narrative_output = await self._narrative_agent.run(context, result.retrieval_output)
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(tool_name=ToolName.NARRATIVE_FEATURE_EXTRACTION),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target == AgentTarget.ROI_PREDICTION:
                if CachedOutputName.ROI in route_plan.cached_outputs_to_use and session_state.roi_output:
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={"summary": session_state.roi_output.summary},
                        )
                    )
                else:
                    result.roi_output = await self._roi_agent.run(
                        context,
                        result.retrieval_output,
                        result.narrative_output,
                    )
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(tool_name=ToolName.SQL_RETRIEVAL),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target == AgentTarget.RISK_CONTRACT_ANALYSIS:
                if CachedOutputName.RISK in route_plan.cached_outputs_to_use and session_state.risk_output:
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={"summary": session_state.risk_output.summary},
                        )
                    )
                else:
                    result.risk_output = await self._risk_agent.run(context, result.retrieval_output)
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(tool_name=ToolName.CLAUSE_EXTRACTION),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target == AgentTarget.CATALOG_FIT:
                if CachedOutputName.CATALOG in route_plan.cached_outputs_to_use and session_state.catalog_output:
                    result.invoked_agents.append(
                        AgentInvocation(
                            target=target,
                            cached=True,
                            details={"summary": session_state.catalog_output.summary},
                        )
                    )
                else:
                    result.catalog_output = await self._catalog_agent.run(context, result.retrieval_output)
                    result.invoked_agents.append(AgentInvocation(target=target))
                    result.invoked_tools.extend(
                        [
                            ToolInvocation(tool_name=ToolName.HYBRID_DOCUMENT_RETRIEVAL),
                            ToolInvocation(tool_name=ToolName.EVIDENCE_PACKAGING),
                        ]
                    )
            elif target in {AgentTarget.RECOMMENDATION_ENGINE, AgentTarget.COMPARISON_SYNTHESIS}:
                dependencies = [
                    invocation.target
                    for invocation in result.invoked_agents
                    if invocation.target not in {AgentTarget.DOCUMENT_RETRIEVAL, target}
                ]
                result.handoffs.append(
                    HandoffOutput(
                        target=target,
                        summary=f"{target.value} handoff prepared for downstream processing.",
                        dependencies=dependencies,
                    )
                )
                result.invoked_agents.append(AgentInvocation(target=target, details={"handoff_only": True}))

        result.warnings.extend(self._warnings_for_missing_outputs(session_state, route_plan))
        logger.info(
            "orchestrator_summary=%s",
            {
                "subagents_invoked": [item.target.value for item in result.invoked_agents],
                "tools_invoked": [item.tool_name.value for item in result.invoked_tools],
                "cache_reuse": [item.target.value for item in result.invoked_agents if item.cached],
                "recomputed": [item.value for item in route_plan.outputs_to_recompute],
            },
        )
        return result

    def build_route_plan(self, query_type: QueryType, session_state: SessionState | None) -> RoutePlan:
        session_state = session_state or SessionState()
        route = ROUTING_MATRIX[query_type]
        cached_outputs_to_use = [
            output_name
            for output_name in route.reusable_outputs
            if self._session_output(session_state, output_name) is not None
        ]
        outputs_to_recompute = list(route.recompute_outputs)
        if query_type == QueryType.FOLLOWUP_WHY_ROI and session_state.roi_output is not None:
            outputs_to_recompute = []
        if query_type == QueryType.FOLLOWUP_WHY_RISK and session_state.risk_output is not None:
            outputs_to_recompute = []
        if query_type == QueryType.FOLLOWUP_WHY_CATALOG and session_state.catalog_output is not None:
            outputs_to_recompute = []

        return RoutePlan(
            query_type=query_type,
            agent_sequence=route.target_agents,
            cached_outputs_to_use=cached_outputs_to_use,
            outputs_to_recompute=outputs_to_recompute,
            active_option_id=self.resolve_active_option(query_type, session_state),
            evaluate_all_comparison_options=query_type == QueryType.COMPARISON,
            support_agents=[AgentTarget.DOCUMENT_RETRIEVAL] if self._needs_document_prefetch(query_type) else [],
        )

    def resolve_active_option(self, query_type: QueryType, session_state: SessionState | None) -> str | None:
        if session_state is None or session_state.comparison_state is None:
            return None
        if query_type == QueryType.COMPARISON:
            return session_state.comparison_state.active_option
        return session_state.active_option or session_state.comparison_state.active_option

    def update_session_state(self, state: SessionState | None, result: OrchestrationResult) -> SessionState:
        current = state or SessionState()
        now = datetime.now(UTC)
        return current.model_copy(
            update={
                "query_type": result.classification.query_type,
                "narrative_output": self._to_session_output(result.narrative_output, now)
                or current.narrative_output,
                "roi_output": self._to_session_output(result.roi_output, now) or current.roi_output,
                "risk_output": self._to_session_output(result.risk_output, now) or current.risk_output,
                "catalog_output": self._to_session_output(result.catalog_output, now)
                or current.catalog_output,
                "active_option": result.active_option_id,
                "retrieval_context": [
                    *(current.retrieval_context or []),
                    *(candidate.section_id for candidate in (result.retrieval_output.raw_candidates if result.retrieval_output else [])),
                ],
            }
        )

    def _comparison_options(self, session_state: SessionState) -> list[ComparisonOption]:
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
        return getattr(session_state, output_name.value)

    def _warnings_for_missing_outputs(
        self,
        session_state: SessionState,
        route_plan: RoutePlan,
    ) -> list[str]:
        warnings: list[str] = []
        for output_name in route_plan.cached_outputs_to_use:
            if self._session_output(session_state, output_name) is None:
                warnings.append(f"Requested cached output {output_name.value} was unavailable.")
        return warnings

    def _to_session_output(self, value: object, generated_at: datetime) -> SessionAgentOutput | None:
        if value is None or not hasattr(value, "summary"):
            return None
        return SessionAgentOutput(summary=str(getattr(value, "summary")), confidence=0.6, generated_at=generated_at)
