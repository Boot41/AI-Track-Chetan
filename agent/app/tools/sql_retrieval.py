from __future__ import annotations

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.app.persistence.tables import structured_metrics
from agent.app.schemas.orchestration import SqlMetricRecord, SqlRetrievalRequest, SqlRetrievalResult

_DEFAULT_METRICS = {
    "baseline_completion_rate": 0.56,
    "comparable_completion_rate": 0.60,
    "baseline_retention_lift": 0.03,
    "projected_viewers": 15000000.0,
    "projected_revenue": 85000000.0,
    "total_cost": 50000000.0,
    "retention_value": 10000000.0,
    "franchise_value": 5000000.0,
}


class SqlRetrievalTool:
    """Retrieves metrics from the structured_metrics table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def run(self, request: SqlRetrievalRequest) -> SqlRetrievalResult:
        request = SqlRetrievalRequest.model_validate(request)
        pitch_id = request.pitch_id or request.active_option_id
        
        # Normalize pitch_id if it's not a standard ID
        if pitch_id and not pitch_id.startswith("pitch_"):
            from agent.app.orchestrator import _infer_pitch_id_from_message
            normalized = _infer_pitch_id_from_message(pitch_id)
            if normalized:
                pitch_id = normalized

        if not pitch_id:
            return self._default_result(request.metric_keys, "no pitch_id provided")

        async with self._session_factory() as session:
            stmt = select(structured_metrics).where(
                and_(
                    structured_metrics.c.pitch_id == pitch_id,
                    structured_metrics.c.metric_key.in_(request.metric_keys)
                )
            )
            result = await session.execute(stmt)
            rows = result.fetchall()
            
            records = []
            found_keys = set()
            for row in rows:
                records.append(
                    SqlMetricRecord(
                        metric_key=row.metric_key,
                        value=row.metric_value,
                        source_table="structured_metrics",
                        source_reference=row.source_reference,
                    )
                )
                found_keys.add(row.metric_key)
            
            warnings = []
            if not found_keys:
                warnings.append(f"No metrics found in DB for pitch '{pitch_id}'; using defaults.")
                for key in request.metric_keys:
                    records.append(
                        SqlMetricRecord(
                            metric_key=key,
                            value=_DEFAULT_METRICS.get(key, 0.0),
                            source_table="defaults",
                            source_reference="internal_logic",
                        )
                    )
            elif len(found_keys) < len(request.metric_keys):
                missing = set(request.metric_keys) - found_keys
                warnings.append(f"Some metrics missing for pitch '{pitch_id}': {', '.join(missing)}")
                for key in missing:
                    records.append(
                        SqlMetricRecord(
                            metric_key=key,
                            value=_DEFAULT_METRICS.get(key, 0.0),
                            source_table="defaults",
                            source_reference="internal_logic",
                        )
                    )
            
            return SqlRetrievalResult(records=records, warnings=warnings)

    def _default_result(self, metric_keys: list[str], reason: str) -> SqlRetrievalResult:
        records = [
            SqlMetricRecord(
                metric_key=key,
                value=_DEFAULT_METRICS.get(key, 0.0),
                source_table="defaults",
                source_reference="internal_logic",
            )
            for key in metric_keys
        ]
        return SqlRetrievalResult(
            records=records, 
            warnings=[f"Using defaults because: {reason}"]
        )
