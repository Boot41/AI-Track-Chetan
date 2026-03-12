from __future__ import annotations

from app.schemas.evaluation import (
    CompletionRateScore,
    CostPerViewInputs,
    RetentionLiftInputs,
    RoiInputs,
    RoiScore,
)


class RoiScorer:
    def score(
        self,
        roi_inputs: RoiInputs,
        retention_inputs: RetentionLiftInputs,
        cost_per_view_inputs: CostPerViewInputs,
        completion_score: CompletionRateScore,
    ) -> RoiScore:
        roi_inputs = RoiInputs.model_validate(roi_inputs)
        retention_inputs = RetentionLiftInputs.model_validate(retention_inputs)
        cost_per_view_inputs = CostPerViewInputs.model_validate(cost_per_view_inputs)
        completion_score = CompletionRateScore.model_validate(completion_score)

        retention_lift = round(
            retention_inputs.baseline_retention_lift
            * (
                1.0
                + 0.35 * retention_inputs.audience_alignment
                + 0.25 * retention_inputs.churn_reduction_signal
                + 0.20 * retention_inputs.franchise_uplift
                + 0.20 * retention_inputs.regional_demand_signal
            ),
            4,
        )
        realized_revenue = (
            roi_inputs.projected_revenue * completion_score.projected_completion_rate
            + roi_inputs.retention_value
            + roi_inputs.franchise_value
        )
        estimated_roi = round(
            (realized_revenue - roi_inputs.total_cost) / roi_inputs.total_cost,
            4,
        )
        cost_per_view = round(
            cost_per_view_inputs.total_cost / cost_per_view_inputs.projected_viewers,
            4,
        )
        return RoiScore(
            estimated_roi=estimated_roi,
            cost_per_view=cost_per_view,
            retention_lift=retention_lift,
            rationale=(
                "Applied completion-adjusted revenue realization, added retention and "
                "franchise value, and normalized unit economics with projected viewers."
            ),
        )
