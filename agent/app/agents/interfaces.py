from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas.orchestration import (
    AgentExecutionContext,
    CatalogAgentOutput,
    NarrativeAgentOutput,
    RetrievalAgentOutput,
    RiskAgentOutput,
    RoiAgentOutput,
)


class DocumentRetrievalAgentInterface(ABC):
    target_name = "document_retrieval"

    @abstractmethod
    async def run(self, context: AgentExecutionContext) -> RetrievalAgentOutput: ...


class NarrativeAnalysisAgentInterface(ABC):
    target_name = "narrative_analysis"

    @abstractmethod
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> NarrativeAgentOutput: ...


class RoiPredictionAgentInterface(ABC):
    target_name = "roi_prediction"

    @abstractmethod
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
        narrative_output: NarrativeAgentOutput | None,
    ) -> RoiAgentOutput: ...


class RiskContractAnalysisAgentInterface(ABC):
    target_name = "risk_contract_analysis"

    @abstractmethod
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> RiskAgentOutput: ...


class CatalogFitAgentInterface(ABC):
    target_name = "catalog_fit"

    @abstractmethod
    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> CatalogAgentOutput: ...

