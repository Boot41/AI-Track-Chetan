from __future__ import annotations

from agent.app.agents.interfaces import (
    CatalogFitAgentInterface,
    DocumentRetrievalAgentInterface,
    NarrativeAnalysisAgentInterface,
    RiskContractAnalysisAgentInterface,
    RoiPredictionAgentInterface,
)
from agent.app.schemas.ingestion import DocumentType
from agent.app.schemas.orchestration import (
    AgentExecutionContext,
    AgentTarget,
    CatalogAgentOutput,
    ClauseExtractionRequest,
    EvidencePackagingRequest,
    HybridDocumentRetrievalRequest,
    NarrativeAgentOutput,
    NarrativeFeatureExtractionRequest,
    RetrievalAgentOutput,
    RiskAgentOutput,
    RoiAgentOutput,
    SqlRetrievalRequest,
)
from agent.app.tools import (
    ClauseExtractionTool,
    EvidencePackagingTool,
    HybridDocumentRetrievalTool,
    NarrativeFeatureExtractionTool,
    SqlRetrievalTool,
)


class DocumentRetrievalAgent(DocumentRetrievalAgentInterface):
    def __init__(
        self,
        hybrid_tool: HybridDocumentRetrievalTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._hybrid_tool = hybrid_tool
        self._provenance_tool = provenance_tool

    async def run(self, context: AgentExecutionContext) -> RetrievalAgentOutput:
        retrieval = await self._hybrid_tool.run(
            HybridDocumentRetrievalRequest(
                query_text=context.request.message,
                content_ids=[context.request.session_state.pitch_id]
                if context.request.session_state and context.request.session_state.pitch_id
                else [],
                limit=6,
            )
        )
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.DOCUMENT_RETRIEVAL,
                claim_it_supports="document retrieval context",
                retrieval_candidates=retrieval.candidates,
            )
        )
        return RetrievalAgentOutput(
            summary=f"Retrieved {len(retrieval.candidates)} supporting sections.",
            evidence=evidence.evidence,
            raw_candidates=retrieval.candidates,
        )


class NarrativeAnalysisAgent(NarrativeAnalysisAgentInterface):
    def __init__(
        self,
        feature_tool: NarrativeFeatureExtractionTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._feature_tool = feature_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> NarrativeAgentOutput:
        candidates = retrieval_output.raw_candidates if retrieval_output else []
        features = await self._feature_tool.run(
            NarrativeFeatureExtractionRequest(
                query_text=context.request.message,
                sections=candidates,
            )
        )
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.NARRATIVE_ANALYSIS,
                claim_it_supports="narrative analysis",
                retrieval_candidates=candidates[:3],
            )
        )
        return NarrativeAgentOutput(
            summary=features.summary,
            features=features.features,
            evidence=evidence.evidence,
        )


class RoiPredictionAgent(RoiPredictionAgentInterface):
    def __init__(
        self,
        sql_tool: SqlRetrievalTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._sql_tool = sql_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
        narrative_output: NarrativeAgentOutput | None,
    ) -> RoiAgentOutput:
        sql_result = await self._sql_tool.run(
            SqlRetrievalRequest(
                pitch_id=context.request.session_state.pitch_id if context.request.session_state else None,
                metric_keys=["completion_rate_proxy", "retention_lift_proxy", "budget_assumption"],
                active_option_id=context.active_option_id,
            )
        )
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.ROI_PREDICTION,
                claim_it_supports="roi prediction assumptions",
                retrieval_candidates=(retrieval_output.raw_candidates[:2] if retrieval_output else []),
                sql_records=sql_result.records,
            )
        )
        assumptions = ["Structured metrics are currently stubbed until scorer tables land."]
        if narrative_output is not None and narrative_output.features:
            assumptions.append(f"Narrative signal seed: {narrative_output.features[0].value}")
        return RoiAgentOutput(
            summary="ROI prediction handoff prepared with current assumptions.",
            assumptions=assumptions,
            metrics=sql_result.records,
            evidence=evidence.evidence,
        )


class RiskContractAnalysisAgent(RiskContractAnalysisAgentInterface):
    def __init__(
        self,
        clause_tool: ClauseExtractionTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._clause_tool = clause_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> RiskAgentOutput:
        clauses = await self._clause_tool.run(
            ClauseExtractionRequest(
                query_text=context.request.message,
                content_ids=[context.request.session_state.pitch_id]
                if context.request.session_state and context.request.session_state.pitch_id
                else [],
                limit=4,
            )
        )
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.RISK_CONTRACT_ANALYSIS,
                claim_it_supports="risk and contract analysis",
                retrieval_candidates=(retrieval_output.raw_candidates[:2] if retrieval_output else []),
            )
        )
        return RiskAgentOutput(
            summary="Contract and risk support prepared from indexed clauses.",
            clauses=clauses.clauses,
            evidence=evidence.evidence,
        )


class CatalogFitAgent(CatalogFitAgentInterface):
    def __init__(
        self,
        hybrid_tool: HybridDocumentRetrievalTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._hybrid_tool = hybrid_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> CatalogAgentOutput:
        strategic_docs = await self._hybrid_tool.run(
            HybridDocumentRetrievalRequest(
                query_text=context.request.message,
                content_ids=[context.request.session_state.pitch_id]
                if context.request.session_state and context.request.session_state.pitch_id
                else [],
                document_types=[DocumentType.REPORT, DocumentType.DECK, DocumentType.CONTRACT],
                limit=3,
            )
        )
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.CATALOG_FIT,
                claim_it_supports="catalog fit analysis",
                retrieval_candidates=strategic_docs.candidates,
            )
        )
        return CatalogAgentOutput(
            summary="Catalog fit context assembled from strategic and market-facing documents.",
            signals=["strategic_gap_alignment", "regional_fit_context"],
            evidence=evidence.evidence,
        )
