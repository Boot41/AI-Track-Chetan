from __future__ import annotations

from ..schemas.evaluation import CatalogFitInputs, CatalogFitScore


class CatalogFitScorer:
    def score(self, inputs: CatalogFitInputs) -> CatalogFitScore:
        inputs = CatalogFitInputs.model_validate(inputs)

        positive = (
            sum(item.strength for item in inputs.underserved_segments) * 18
            + sum(item.strength for item in inputs.churn_demographics) * 18
            + sum(item.strength for item in inputs.genre_gaps) * 20
            + sum(item.strength for item in inputs.regional_demand) * 16
            + sum(item.strength for item in inputs.strategic_timing) * 16
            + sum(item.strength for item in inputs.localization_implications) * 12
        )
        overlap_penalty = sum(item.strength for item in inputs.competitor_overlap) * 20
        score = min(100.0, max(0.0, round(positive - overlap_penalty, 2)))
        return CatalogFitScore(
            score=score,
            rationale=(
                "Scored positive strategic demand signals and subtracted competitor "
                "overlap pressure to keep the fit decision auditable."
            ),
        )
