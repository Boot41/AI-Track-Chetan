from __future__ import annotations

import asyncio
import re

from sqlalchemy import Select, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.app.persistence.tables import document_sections, documents
from agent.app.retrieval.embeddings import HashEmbeddingService, cosine_similarity
from agent.app.retrieval.ranking import reciprocal_rank_fusion, rerank_candidates
from agent.app.schemas.ingestion import DocumentType, RetrievalMethod
from agent.app.schemas.retrieval import RetrievalCandidate, RetrievalQuery


class HybridRetriever:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: HashEmbeddingService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_service = embedding_service or HashEmbeddingService()

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalCandidate]:
        query_embedding = self._embedding_service.embed_text(query.query_text)
        filtered_ids = await self._metadata_filter(query)
        fts_results, vector_results = await asyncio.gather(
            self._fts_search(query, filtered_ids),
            self._vector_search(query, filtered_ids, query_embedding),
        )

        fts_ids = [item["section_id"] for item in fts_results]
        vector_ids = [item["section_id"] for item in vector_results]
        weight_map = {
            item["section_id"]: float(item["doc_type_weight"])
            for item in fts_results + vector_results
        }
        fusion_scores = reciprocal_rank_fusion([fts_ids, vector_ids], per_item_weight=weight_map)

        merged: dict[str, dict[str, object]] = {}
        for result in fts_results + vector_results:
            current = merged.setdefault(result["section_id"], result.copy())
            current["seen_methods"] = set(current.get("seen_methods", set())) | {result["retrieval_method"]}
            current["method_score"] = max(
                float(current.get("method_score", 0.0)),
                float(result["method_score"]),
            )
            current["fusion_score"] = fusion_scores.get(result["section_id"], 0.0)

        reranked = rerank_candidates(list(merged.values()), limit=query.limit)
        output: list[RetrievalCandidate] = []
        for item in reranked:
            methods = item["seen_methods"]
            if len(methods) > 1:
                retrieval_method = RetrievalMethod.HYBRID
            elif RetrievalMethod.FTS in methods:
                retrieval_method = RetrievalMethod.FTS
            else:
                retrieval_method = RetrievalMethod.VECTOR

            confidence = min(
                1.0,
                max(
                    0.05,
                    float(item["fusion_score"]) * 25 + float(item["method_score"]) * 0.45,
                ),
            )
            output.append(
                RetrievalCandidate(
                    document_id=str(item["document_id"]),
                    section_id=str(item["section_id"]),
                    snippet=str(item["snippet"]),
                    source_reference=str(item["source_reference"]),
                    retrieval_method=retrieval_method,
                    confidence_score=round(confidence, 4),
                    document_type=DocumentType(str(item["document_type"])),
                    claim_support_metadata={
                        "source_path": item["source_path"],
                        "section_type": item["section_type"],
                        "structure_confidence": item["structure_confidence"],
                        "matched_methods": sorted(method.value for method in methods),
                    },
                )
            )
        return output

    async def _metadata_filter(self, query: RetrievalQuery) -> list[str]:
        stmt: Select[tuple[str]] = select(documents.c.id)
        if query.content_ids:
            stmt = stmt.where(documents.c.content_id.in_(query.content_ids))
        if query.document_types:
            stmt = stmt.where(documents.c.document_type.in_([item.value for item in query.document_types]))
        if query.source_paths:
            stmt = stmt.where(documents.c.source_path.in_(query.source_paths))
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()
        return [row[0] for row in rows]

    async def _fts_search(self, query: RetrievalQuery, document_ids: list[str]) -> list[dict[str, object]]:
        if not document_ids:
            return []
        tokens = re.findall(r"[a-z0-9]+", query.query_text.lower())
        if not tokens:
            return []
        ts_query = " | ".join(tokens)
        search_vector = func.to_tsvector(
            "english",
            func.concat(
                func.coalesce(document_sections.c.title, literal("")),
                literal(" "),
                document_sections.c.content,
            ),
        )
        query_vector = func.to_tsquery("english", ts_query)
        stmt = (
            select(
                documents.c.id.label("document_id"),
                documents.c.document_type.label("document_type"),
                documents.c.source_path.label("source_path"),
                document_sections.c.id.label("section_id"),
                document_sections.c.section_type.label("section_type"),
                document_sections.c.source_reference.label("source_reference"),
                document_sections.c.content.label("snippet"),
                document_sections.c.structure_confidence.label("structure_confidence"),
                func.ts_rank_cd(search_vector, query_vector).label("method_score"),
            )
            .join(documents, document_sections.c.document_id == documents.c.id)
            .where(documents.c.id.in_(document_ids))
            .where(search_vector.op("@@")(query_vector))
            .order_by(func.ts_rank_cd(search_vector, query_vector).desc())
            .limit(query.limit * 3)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [self._normalize_result(row, RetrievalMethod.FTS, query) for row in rows]

    async def _vector_search(
        self,
        query: RetrievalQuery,
        document_ids: list[str],
        query_embedding: list[float],
    ) -> list[dict[str, object]]:
        if not document_ids:
            return []
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(
                        documents.c.id.label("document_id"),
                        documents.c.document_type.label("document_type"),
                        documents.c.source_path.label("source_path"),
                        document_sections.c.id.label("section_id"),
                        document_sections.c.section_type.label("section_type"),
                        document_sections.c.source_reference.label("source_reference"),
                        document_sections.c.content.label("snippet"),
                        document_sections.c.structure_confidence.label("structure_confidence"),
                        document_sections.c.embedding.label("embedding"),
                    )
                    .join(documents, document_sections.c.document_id == documents.c.id)
                    .where(documents.c.id.in_(document_ids))
                    .where(document_sections.c.embedding.is_not(None))
                )
            ).mappings().all()

        scored: list[dict[str, object]] = []
        for row in rows:
            embedding = row["embedding"]
            if not isinstance(embedding, list):
                continue
            score = cosine_similarity(query_embedding, [float(value) for value in embedding])
            if score <= 0:
                continue
            normalized = self._normalize_result(row, RetrievalMethod.VECTOR, query)
            normalized["method_score"] = score
            scored.append(normalized)
        scored.sort(key=lambda item: float(item["method_score"]), reverse=True)
        return scored[: query.limit * 3]

    def _normalize_result(
        self,
        row: dict[str, object],
        method: RetrievalMethod,
        query: RetrievalQuery,
    ) -> dict[str, object]:
        doc_type = DocumentType(str(row["document_type"]))
        return {
            "document_id": row["document_id"],
            "section_id": row["section_id"],
            "source_path": row["source_path"],
            "section_type": row["section_type"],
            "source_reference": row["source_reference"],
            "snippet": str(row["snippet"])[:280],
            "document_type": doc_type.value,
            "structure_confidence": float(row["structure_confidence"]),
            "retrieval_method": method,
            "method_score": float(row.get("method_score", 0.0)),
            "fusion_score": 0.0,
            "doc_type_weight": query.per_document_type_weight.get(doc_type, 1.0),
        }
