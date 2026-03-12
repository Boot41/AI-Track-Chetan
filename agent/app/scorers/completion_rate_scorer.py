from __future__ import annotations

from app.schemas.evaluation import CompletionRateInputs, CompletionRateScore


class CompletionRateScorer:
    def score(self, inputs: CompletionRateInputs) -> CompletionRateScore:
        inputs = CompletionRateInputs.model_validate(inputs)
        projected = (
            inputs.baseline_completion_rate * 0.45
            + inputs.comparable_completion_rate * 0.35
            + inputs.hook_strength * 0.12
            + inputs.bingeability * 0.08
            - inputs.pacing_penalty * 0.10
            - inputs.narrative_clarity_penalty * 0.08
        )
        projected = min(0.95, max(0.05, round(projected, 4)))
        return CompletionRateScore(
            projected_completion_rate=projected,
            rationale=(
                "Combined the structured baseline, comparable-title baseline, and "
                "narrative hooks while penalizing pacing and clarity risks."
            ),
        )
