from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.retrieval.hybrid import HybridRetriever
from app.schemas.orchestration import (
    HybridDocumentRetrievalRequest,
    HybridDocumentRetrievalResult,
)
from app.schemas.retrieval import RetrievalQuery


class HybridDocumentRetrievalTool:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._retriever = HybridRetriever(session_factory)

    async def run(self, request: HybridDocumentRetrievalRequest) -> HybridDocumentRetrievalResult:
        request = HybridDocumentRetrievalRequest.model_validate(request)
        candidates = await self._retriever.retrieve(
            RetrievalQuery(
                query_text=request.query_text,
                content_ids=request.content_ids,
                document_types=request.document_types,
                limit=request.limit,
            )
        )
        return HybridDocumentRetrievalResult(candidates=candidates)

