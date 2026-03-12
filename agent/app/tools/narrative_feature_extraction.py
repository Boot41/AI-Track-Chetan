from __future__ import annotations

from collections import Counter

from ..schemas.orchestration import (
    NarrativeFeature,
    NarrativeFeatureExtractionRequest,
    NarrativeFeatureExtractionResult,
)


class NarrativeFeatureExtractionTool:
    async def run(self, request: NarrativeFeatureExtractionRequest) -> NarrativeFeatureExtractionResult:
        request = NarrativeFeatureExtractionRequest.model_validate(request)
        joined_text = " ".join(candidate.snippet.lower() for candidate in request.sections)

        theme_terms: Counter[str] = Counter()
        potential_themes = {
            "thriller": ("thriller", "suspense", "tension"),
            "mystery": ("mystery", "puzzle", "investigation"),
            "noir": ("noir", "dark", "gritty", "shadow"),
            "cyber": ("cyber", "tech", "digital", "hack"),
            "drama": ("drama", "emotional", "character study"),
            "action": ("action", "fight", "chase"),
            "espionage": ("espionage", "spy", "conspiracy", "nsa"),
            "family": ("family", "parent", "child", "sibling"),
            "romance": ("romance", "love", "relationship"),
        }
        
        for theme, tokens in potential_themes.items():
            for token in tokens:
                if token in joined_text:
                    theme_terms[theme] += joined_text.count(token)

        dominant = theme_terms.most_common(1)
        features = [
            NarrativeFeature(
                name="dominant_theme",
                value=dominant[0][0] if dominant else "undetermined",
                confidence=0.8 if dominant else 0.2,
                rationale=f"Derived from keyword analysis (found {len(theme_terms)} theme signals).",
            ),
            NarrativeFeature(
                name="story_focus",
                value="character-driven" if any(t in joined_text for t in ("arc", "protagonist", "journey", "growth")) else "concept-driven",
                confidence=0.7,
                rationale="Heuristic based on presence of character development terminology.",
            ),
            NarrativeFeature(
                name="tone",
                value="gritty/realistic" if any(t in joined_text for t in ("gritty", "realistic", "grounded")) else "stylized",
                confidence=0.6,
                rationale="Tone inferred from stylistic keywords in source text.",
            ),
        ]
        return NarrativeFeatureExtractionResult(
            features=features,
            summary=f"Narrative analysis complete. Found {len(theme_terms)} themes. Focus is {features[1].value}.",
        )
