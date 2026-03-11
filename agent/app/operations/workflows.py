from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.app.ingestion.inventory import RAW_DATA_ROOT
from agent.app.persistence.tables import documents
from agent.app.schemas.ingestion import IngestionStatus


@dataclass(slots=True)
class CorpusIndexState:
    fingerprint: str
    document_count: int
    last_indexed_at: datetime | None
    warnings: list[str]


@dataclass(slots=True)
class CompetitorCatalogState:
    source_count: int
    refreshed_at: datetime | None
    stale: bool
    warnings: list[str]


class OperationalDataWorkflow:
    """Operational helpers for reindexing, cache invalidation, and freshness checks."""

    _COMPETITOR_STALE_DAYS = 14

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _safe_source_mtime(source_path: str) -> datetime | None:
        try:
            ts = Path(source_path).stat().st_mtime
        except OSError:
            return None
        return datetime.fromtimestamp(ts, UTC).replace(tzinfo=None)

    @staticmethod
    def _indexed_at_from_metadata(metadata: object) -> datetime | None:
        if not isinstance(metadata, dict):
            return None
        raw_value = metadata.get("indexed_at")
        if not isinstance(raw_value, str) or not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        return parsed.replace(tzinfo=None)

    async def corpus_index_state(self) -> CorpusIndexState:
        warnings: list[str] = []
        try:
            async with self._session_factory() as session:
                row = (
                    await session.execute(
                        select(
                            func.count().label("count"),
                        )
                    )
                ).one()
                count_value = row._mapping["count"]
                status_rows = (
                    await session.execute(
                        select(
                            documents.c.id,
                            documents.c.ingestion_status,
                            documents.c.source_path,
                            documents.c.source_metadata,
                        ).order_by(documents.c.id.asc())
                    )
                ).all()
        except Exception:
            return CorpusIndexState(
                fingerprint="unavailable",
                document_count=0,
                last_indexed_at=None,
                warnings=["Could not load document index state from persistence."],
            )

        indexed_times: list[datetime] = []
        for _doc_id, _status, source_path, source_metadata in status_rows:
            metadata_time = self._indexed_at_from_metadata(cast(dict[str, Any] | None, source_metadata))
            if metadata_time is not None:
                indexed_times.append(metadata_time)
                continue
            source_mtime = self._safe_source_mtime(source_path)
            if source_mtime is not None:
                indexed_times.append(source_mtime)
        last_indexed_at = max(indexed_times, default=None)
        payload = "|".join(
            f"{doc_id}:{status}:{source_path}"
            for doc_id, status, source_path, _source_metadata in status_rows
        )
        fingerprint_seed = payload if payload else "empty-index"
        fingerprint = hashlib.sha1(fingerprint_seed.encode("utf-8")).hexdigest()[:16]
        failed = [
            doc_id
            for doc_id, status, _source_path, _source_metadata in status_rows
            if status in {IngestionStatus.FAILED.value, IngestionStatus.PARTIAL.value}
        ]
        if failed:
            warnings.append(
                "Document index contains failed or partial ingestion results; run reindex before relying on cached outputs."
            )
        if count_value == 0:
            warnings.append("Document index is empty; retrieval confidence may be low.")

        return CorpusIndexState(
            fingerprint=fingerprint,
            document_count=int(count_value),
            last_indexed_at=last_indexed_at,
            warnings=warnings,
        )

    async def competitor_catalog_state(self) -> CompetitorCatalogState:
        warnings: list[str] = []
        state = await self.corpus_index_state()
        try:
            async with self._session_factory() as session:
                rows = (
                    await session.execute(
                        select(documents.c.source_path, documents.c.source_metadata).where(
                            documents.c.filename.ilike("%comp_titles%")
                        )
                    )
                ).all()
        except Exception:
            rows = []
            warnings.append("Could not inspect competitor catalog freshness in persistence.")

        refreshed_at = max(
            (
                candidate_time
                for row in rows
                if (
                    candidate_time := (
                        self._indexed_at_from_metadata(cast(dict[str, Any] | None, row.source_metadata))
                        or self._safe_source_mtime(row.source_path)
                    )
                )
                is not None
            ),
            default=None,
        )
        stale = True
        if refreshed_at is not None:
            age = datetime.now(UTC).replace(tzinfo=None) - refreshed_at
            stale = age.days >= self._COMPETITOR_STALE_DAYS

        if not rows:
            warnings.append("No competitor catalog source files were indexed.")
        elif stale:
            warnings.append(
                "Competitor catalog signals may be stale; refresh comp-title notes and rerun ingestion."
            )
        warnings.extend(state.warnings)
        return CompetitorCatalogState(
            source_count=len(rows),
            refreshed_at=refreshed_at,
            stale=stale,
            warnings=list(dict.fromkeys(warnings)),
        )

    def source_fingerprint(self, raw_root: Path = RAW_DATA_ROOT) -> str:
        entries: list[str] = []
        for path in sorted(raw_root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            entries.append(f"{path.relative_to(raw_root)}:{int(stat.st_mtime)}:{stat.st_size}")
        digest_input = "|".join(entries)
        return hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:16]
