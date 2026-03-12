from __future__ import annotations

import re

from agent.app.agents.routing import ROUTING_MATRIX
from agent.app.schemas.orchestration import QueryClassification, QueryType, SessionState


class QueryClassifier:
    """Deterministic classifier kept explicit for testability."""

    def classify(
        self, message: str, session_state: SessionState | None = None
    ) -> QueryClassification:
        normalized = self._normalize(message)
        query_type = self._classify_query_type(normalized, session_state)
        route = ROUTING_MATRIX[query_type]

        reuse_cached_outputs = bool(route.reusable_outputs)
        requires_recomputation = bool(route.recompute_outputs) and query_type in {
            QueryType.ORIGINAL_EVAL,
            QueryType.ACQUISITION_EVAL,
            QueryType.COMPARISON,
            QueryType.SCENARIO_CHANGE_BUDGET,
            QueryType.SCENARIO_CHANGE_LOCALIZATION,
        }
        if query_type in {
            QueryType.FOLLOWUP_WHY_ROI,
            QueryType.FOLLOWUP_WHY_RISK,
            QueryType.FOLLOWUP_WHY_CATALOG,
        }:
            requires_recomputation = not self._has_required_cache(
                query_type, session_state
            )

        if query_type == QueryType.FOLLOWUP_WHY_NARRATIVE:
            requires_recomputation = not self._has_required_cache(
                query_type, session_state
            )

        return QueryClassification(
            query_type=query_type,
            target_agents=route.target_agents,
            reuse_cached_outputs=reuse_cached_outputs,
            requires_recomputation=requires_recomputation,
        )

    def _classify_query_type(
        self, message: str, session_state: SessionState | None
    ) -> QueryType:
        if any(
            token in message
            for token in ("compare", "versus", " vs ", "better investment")
        ):
            return QueryType.COMPARISON
        if self._looks_like_narrative_deep_dive(message):
            return QueryType.FOLLOWUP_WHY_NARRATIVE
        if self._looks_like_budget_scenario(message):
            return QueryType.SCENARIO_CHANGE_BUDGET
        if self._looks_like_localization_scenario(message):
            return QueryType.SCENARIO_CHANGE_LOCALIZATION
        if self._looks_like_followup(message):
            return self._followup_type(message, session_state)
        
        original_signals = ("greenlight", "original", "series", "pilot", "show bible")
        acquisition_signals = (
            "acquire",
            "acquisition",
            "license",
            "licensing",
            "rights",
            "term sheet",
            "contract",
            "ip ownership",
            "ownership",
            "territory",
            "territories",
            "exclusivity",
            "matching rights",
            "spin-off",
            "spinoff",
            "sequel",
            "prequel",
            "collection",
        )
        
        has_original_keyword = any(token in message for token in original_signals)
        has_acquisition_keyword = any(token in message for token in acquisition_signals)
        
        is_shadow_protocol = "shadow protocol" in message
        is_red_harbor = "red harbor" in message
        
        # Expanded evaluation indicators
        is_evaluation_request = any(
            token in message 
            for token in ("evaluation", "eval ", "roi", "return", "performance", "financial", "viability")
        ) or message.endswith("eval")

        if is_shadow_protocol:
            if is_evaluation_request or has_original_keyword:
                return QueryType.ORIGINAL_EVAL
        
        if is_red_harbor:
            if is_evaluation_request or has_acquisition_keyword:
                return QueryType.ACQUISITION_EVAL

        if has_original_keyword:
            return QueryType.ORIGINAL_EVAL
        if (
            has_acquisition_keyword
            or ("catalog" in message and not has_original_keyword)
        ):
            return QueryType.ACQUISITION_EVAL
            
        return QueryType.GENERAL_QUESTION

    def _followup_type(
        self, message: str, session_state: SessionState | None
    ) -> QueryType:
        keyword_map = {
            QueryType.FOLLOWUP_WHY_NARRATIVE: (
                "narrative",
                "story",
                "theme",
                "tone",
                "character",
            ),
            QueryType.FOLLOWUP_WHY_ROI: (
                "roi",
                "return",
                "completion",
                "retention",
                "budget",
            ),
            QueryType.FOLLOWUP_WHY_RISK: (
                "risk",
                "contract",
                "rights",
                "regulatory",
                "clause",
            ),
            QueryType.FOLLOWUP_WHY_CATALOG: (
                "catalog",
                "fit",
                "demographic",
                "strategy",
                "audience",
            ),
        }
        for query_type, keywords in keyword_map.items():
            if any(keyword in message for keyword in keywords):
                return query_type

        if session_state and session_state.query_type:
            fallback_map = {
                QueryType.ORIGINAL_EVAL: QueryType.FOLLOWUP_WHY_NARRATIVE,
                QueryType.ACQUISITION_EVAL: QueryType.FOLLOWUP_WHY_RISK,
                QueryType.COMPARISON: QueryType.FOLLOWUP_WHY_ROI,
            }
            return fallback_map.get(
                session_state.query_type, QueryType.GENERAL_QUESTION
            )
        return QueryType.GENERAL_QUESTION

    def _has_required_cache(
        self, query_type: QueryType, session_state: SessionState | None
    ) -> bool:
        if session_state is None:
            return False
        cache_map = {
            QueryType.FOLLOWUP_WHY_NARRATIVE: session_state.narrative_output,
            QueryType.FOLLOWUP_WHY_ROI: session_state.roi_output,
            QueryType.FOLLOWUP_WHY_RISK: session_state.risk_output,
            QueryType.FOLLOWUP_WHY_CATALOG: session_state.catalog_output,
        }
        return cache_map.get(query_type) is not None

    def _looks_like_followup(self, message: str) -> bool:
        return message.startswith("why") or "why " in message or "explain" in message

    def _looks_like_narrative_deep_dive(self, message: str) -> bool:
        prompt_verbs = (
            "describe",
            "summarize",
            "analyse",
            "analyze",
            "break down",
            "walk me through",
            "tell me",
        )
        narrative_targets = (
            "character arc",
            "protagonist",
            "narrative",
            "theme",
            "tone",
            "pacing",
            "pilot script",
            "subtext",
            "dialogue",
            "scene",
            "character depth",
        )
        return any(verb in message for verb in prompt_verbs) and any(
            target in message for target in narrative_targets
        )

    def _looks_like_budget_scenario(self, message: str) -> bool:
        return "budget" in message and bool(
            re.search(
                r"\b(what if|changes? if|change|increase|increases|decrease|decreases|cut)\b",
                message,
            )
        )

    def _looks_like_localization_scenario(self, message: str) -> bool:
        return any(
            token in message
            for token in ("dub", "subtit", "localization", "bahasa", "hindi")
        )

    def _normalize(self, message: str) -> str:
        return re.sub(r"\s+", " ", message.strip().lower())
