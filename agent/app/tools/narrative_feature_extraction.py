from __future__ import annotations

from collections import Counter

from app.schemas.orchestration import (
    NarrativeFeature,
    NarrativeFeatureExtractionRequest,
    NarrativeFeatureExtractionResult,
)


class NarrativeFeatureExtractionTool:
    async def run(self, request: NarrativeFeatureExtractionRequest) -> NarrativeFeatureExtractionResult:
        request = NarrativeFeatureExtractionRequest.model_validate(request)
        joined_text = " ".join(candidate.snippet.lower() for candidate in request.sections)

        theme_terms: Counter[str] = Counter()
        for token in ("thriller", "mystery", "crime", "family", "romance", "comedy", "drama"):
            if token in joined_text:
                theme_terms[token] += joined_text.count(token)

        features = [
            NarrativeFeature(
                name="dominant_theme",
                value=theme_terms.most_common(1)[0][0] if theme_terms else "undetermined",
                confidence=0.7 if theme_terms else 0.2,
                rationale="Derived from repeated narrative terms in retrieved sections.",
            ),
            NarrativeFeature(
                name="story_focus",
                value="character-driven" if "character" in joined_text else "concept-driven",
                confidence=0.6,
                rationale="Lightweight heuristic based on retrieved evidence.",
            ),
        ]
        return NarrativeFeatureExtractionResult(
            features=features,
            summary="Narrative features extracted from retrieved sections.",
        )
