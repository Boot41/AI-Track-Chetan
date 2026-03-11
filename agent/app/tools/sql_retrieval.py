from __future__ import annotations

from agent.app.schemas.orchestration import SqlMetricRecord, SqlRetrievalRequest, SqlRetrievalResult


class SqlRetrievalTool:
    """Structured metrics stub until dedicated business tables are added."""

    async def run(self, request: SqlRetrievalRequest) -> SqlRetrievalResult:
        request = SqlRetrievalRequest.model_validate(request)
        records: list[SqlMetricRecord] = []
        if request.pitch_id:
            for key in request.metric_keys:
                records.append(
                    SqlMetricRecord(
                        metric_key=key,
                        value="unavailable_in_current_metrics_store",
                        source_table="structured_metrics_stub",
                        source_reference=f"pitch:{request.pitch_id}",
                    )
                )
        warnings = [] if records else ["No structured business metric tables are available yet."]
        return SqlRetrievalResult(records=records, warnings=warnings)
