from __future__ import annotations

from agent.app.schemas.orchestration import SqlMetricRecord, SqlRetrievalRequest, SqlRetrievalResult

_SEEDED_METRICS: dict[str, dict[str, float]] = {
    "pitch_shadow_protocol": {
        "baseline_completion_rate": 0.67,
        "comparable_completion_rate": 0.71,
        "baseline_retention_lift": 0.041,
        "projected_viewers": 18000000.0,
        "projected_revenue": 152000000.0,
        "total_cost": 64000000.0,
        "retention_value": 16500000.0,
        "franchise_value": 18000000.0,
    },
    "pitch_red_harbor": {
        "baseline_completion_rate": 0.58,
        "comparable_completion_rate": 0.63,
        "baseline_retention_lift": 0.033,
        "projected_viewers": 24500000.0,
        "projected_revenue": 92000000.0,
        "total_cost": 41000000.0,
        "retention_value": 14000000.0,
        "franchise_value": 7000000.0,
    },
}

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
    """Deterministic metrics seed until dedicated structured metric tables are wired in."""

    async def run(self, request: SqlRetrievalRequest) -> SqlRetrievalResult:
        request = SqlRetrievalRequest.model_validate(request)
        seed_key = request.pitch_id or request.active_option_id or ""
        metrics = _SEEDED_METRICS.get(seed_key, _DEFAULT_METRICS)

        records = [
            SqlMetricRecord(
                metric_key=key,
                value=metrics.get(key, _DEFAULT_METRICS.get(key, 0.0)),
                source_table="structured_metrics_seed",
                source_reference=f"metrics:{seed_key or 'default'}",
            )
            for key in request.metric_keys
        ]
        warnings = [] if request.pitch_id in _SEEDED_METRICS else [
            "Structured metric tables are not present yet; using deterministic seeded metrics."
        ]
        return SqlRetrievalResult(records=records, warnings=warnings)
