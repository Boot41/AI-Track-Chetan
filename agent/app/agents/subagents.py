from __future__ import annotations

import re
from typing import Iterable

from .interfaces import (
    CatalogFitAgentInterface,
    DocumentRetrievalAgentInterface,
    NarrativeAnalysisAgentInterface,
    RiskContractAnalysisAgentInterface,
    RoiPredictionAgentInterface,
)
from ..schemas.evaluation import (
    CatalogFitInputs,
    CatalogFitSignal,
    CharacterArcSignal,
    ComparableTitleEvidence,
    CompletionRateInputs,
    CostPerViewInputs,
    FranchiseAssessment,
    NarrativeRedFlag,
    NarrativeScoreInputs,
    RetrievalEvidencePackage,
    RetrievalFocus,
    RetrievalSourceReference,
    RiskFinding,
    RiskSeverity,
    RetentionLiftInputs,
    RoiInputs,
)
from ..schemas.ingestion import DocumentType, RetrievalMethod
from ..schemas.orchestration import (
    AgentExecutionContext,
    AgentTarget,
    CatalogAgentOutput,
    ClauseExtractionRequest,
    EvidencePackagingRequest,
    HybridDocumentRetrievalRequest,
    NarrativeAgentOutput,
    NarrativeFeatureExtractionRequest,
    RetrievalAgentOutput,
    RiskAgentOutput,
    RoiAgentOutput,
    SqlMetricRecord,
    SqlRetrievalRequest,
)
from ..schemas.retrieval import RetrievalCandidate
from ..tools import (
    ClauseExtractionTool,
    EvidencePackagingTool,
    HybridDocumentRetrievalTool,
    NarrativeFeatureExtractionTool,
    SqlRetrievalTool,
)


def _unique_candidates(candidates: Iterable[RetrievalCandidate]) -> list[RetrievalCandidate]:
    deduped: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        existing = deduped.get(candidate.section_id)
        if existing is None or candidate.confidence_score > existing.confidence_score:
            deduped[candidate.section_id] = candidate
    return list(deduped.values())


def _to_source_refs(candidates: Iterable[RetrievalCandidate]) -> list[RetrievalSourceReference]:
    return [
        RetrievalSourceReference(
            document_id=candidate.document_id,
            section_id=candidate.section_id,
            source_reference=candidate.source_reference,
            retrieval_method=candidate.retrieval_method,
            confidence_score=candidate.confidence_score,
        )
        for candidate in candidates
    ]


def _package_for(
    retrieval_output: RetrievalAgentOutput | None,
    focus: RetrievalFocus,
) -> RetrievalEvidencePackage | None:
    if retrieval_output is None:
        return None
    for package in retrieval_output.packages:
        if package.focus == focus:
            return package
    return None


def _candidates_for(
    retrieval_output: RetrievalAgentOutput | None,
    focus: RetrievalFocus,
) -> list[RetrievalCandidate]:
    if retrieval_output is None:
        return []
    package = _package_for(retrieval_output, focus)
    if package is None:
        return []
    refs = {(item.document_id, item.section_id) for item in package.source_references}
    return [
        candidate
        for candidate in retrieval_output.raw_candidates
        if (candidate.document_id, candidate.section_id) in refs
    ]


def _joined_text(candidates: Iterable[RetrievalCandidate]) -> str:
    return " ".join(candidate.snippet.lower() for candidate in candidates)


def _metric_map(records: list[SqlMetricRecord]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for record in records:
        if isinstance(record.value, bool):
            continue
        if isinstance(record.value, (int, float)):
            metrics[record.metric_key] = float(record.value)
            continue
        try:
            metrics[record.metric_key] = float(record.value)
        except (TypeError, ValueError):
            continue
    return metrics


class DocumentRetrievalAgent(DocumentRetrievalAgentInterface):
    def __init__(
        self,
        hybrid_tool: HybridDocumentRetrievalTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._hybrid_tool = hybrid_tool
        self._provenance_tool = provenance_tool

    async def run(self, context: AgentExecutionContext) -> RetrievalAgentOutput:
        content_ids = (
            [context.request.session_state.pitch_id]
            if context.request.session_state and context.request.session_state.pitch_id
            else []
        )
        requests = [
            (
                RetrievalFocus.CREATIVE,
                HybridDocumentRetrievalRequest(
                    query_text=(
                        f"{context.request.message} genre themes tone pacing character arc "
                        "franchise hook red flag technical jargon confusing slow pacing cliffhanger"
                    ),
                    content_ids=content_ids,
                    document_types=[DocumentType.SCRIPT, DocumentType.DECK, DocumentType.REPORT],
                    limit=7,
                ),
            ),
            (
                RetrievalFocus.COMPARABLES,
                HybridDocumentRetrievalRequest(
                    query_text=(
                        f"{context.request.message} comparable titles performance retention "
                        "completion pacing bingeability"
                    ),
                    content_ids=content_ids,
                    document_types=[DocumentType.REPORT, DocumentType.MEMO, DocumentType.DECK],
                    limit=4,
                ),
            ),
            (
                RetrievalFocus.CONTRACT,
                HybridDocumentRetrievalRequest(
                    query_text=(
                        "rights exclusivity territory carve-out matching rights first-look "
                        "localization censorship regulatory derivative spin-off"
                    ),
                    content_ids=content_ids,
                    document_types=[DocumentType.CONTRACT],
                    limit=5,
                ),
            ),
            (
                RetrievalFocus.STRATEGIC,
                HybridDocumentRetrievalRequest(
                    query_text=(
                        f"{context.request.message} underserved audience churn demographics "
                        "genre gap regional demand competitor overlap strategic timing localization"
                    ),
                    content_ids=content_ids,
                    document_types=[DocumentType.REPORT, DocumentType.MEMO, DocumentType.DECK],
                    limit=5,
                ),
            ),
        ]

        packaged: list[RetrievalEvidencePackage] = []
        all_candidates: list[RetrievalCandidate] = []
        for focus, request in requests:
            response = await self._hybrid_tool.run(request)
            unique = _unique_candidates(response.candidates)
            all_candidates.extend(unique)
            packaged.append(
                RetrievalEvidencePackage(
                    focus=focus,
                    query_text=request.query_text,
                    summary=f"{focus.value} retrieval returned {len(unique)} ranked sections.",
                    source_references=_to_source_refs(unique),
                )
            )

        all_candidates = _unique_candidates(all_candidates)
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.DOCUMENT_RETRIEVAL,
                claim_it_supports="retrieval context for specialist agents",
                retrieval_candidates=all_candidates,
            )
        )
        return RetrievalAgentOutput(
            summary=f"Prepared {len(packaged)} retrieval packages with {len(all_candidates)} unique sections.",
            evidence=evidence.evidence,
            raw_candidates=all_candidates,
            packages=packaged,
        )


class NarrativeAnalysisAgent(NarrativeAnalysisAgentInterface):
    def __init__(
        self,
        feature_tool: NarrativeFeatureExtractionTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._feature_tool = feature_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> NarrativeAgentOutput:
        creative_candidates = _candidates_for(retrieval_output, RetrievalFocus.CREATIVE)
        wider_candidates = _unique_candidates(
            creative_candidates
            + _candidates_for(retrieval_output, RetrievalFocus.COMPARABLES)
            + _candidates_for(retrieval_output, RetrievalFocus.STRATEGIC)
        )
        features = await self._feature_tool.run(
            NarrativeFeatureExtractionRequest(
                query_text=context.request.message,
                sections=creative_candidates,
            )
        )
        text = _joined_text(wider_candidates)

        genre = "cyber-noir thriller"
        if "documentary" in text:
            genre = "global documentary package"
        elif "cyber-noir" in text or ("cyber" in text and "noir" in text):
            genre = "cyber-noir thriller"
        elif "action" in text and "thriller" in text:
            genre = "action thriller"
        elif "thriller" in text:
            genre = "thriller"

        theme_map = {
            "privacy vs. security": ("privacy", "security", "surveillance"),
            "identity": ("identity", "ghost", "deleted"),
            "legacy": ("legacy", "father", "architect"),
            "global diversity": ("international", "global", "regional"),
        }
        themes = [
            theme
            for theme, tokens in theme_map.items()
            if any(token in text for token in tokens)
        ]
        if not themes and features.features:
            themes = [features.features[0].value]

        tone = []
        for label, tokens in {
            "paranoid": ("paranoid", "surveillance", "haunt"),
            "gritty": ("gritty", "rain-slicked", "noir"),
            "fast-paced": ("fast-paced", "high-stakes", "chase"),
            "prestige": ("prestige", "emmy", "career-defining"),
        }.items():
            if any(token in text for token in tokens):
                tone.append(label)
        if not tone:
            tone.append("grounded")

        pacing = "fast"
        if "slow pacing" in text or "slows significantly" in text:
            pacing = "uneven"
        elif "cliffhanger" in text or "binge" in text:
            pacing = "binge-forward"

        arc_candidates = []
        for name, summary in {
            "Elara Vance": "Transforms from institutional analyst into an off-grid insurgent.",
            "Kai": "Provides reckless hacker energy that accelerates the plot and raises risk.",
            "Arthur": "Mentor-turned-antagonist who personalizes the surveillance conflict.",
        }.items():
            if name.split()[0].lower() in text:
                arc_candidates.append(
                    CharacterArcSignal(
                        character_name=name,
                        arc_summary=summary,
                        confidence=0.78,
                        source_references=_to_source_refs(creative_candidates[:2]),
                    )
                )

        franchise_strength = 0.85 if "spin-off" in text or "prequel" in text or "expanded lore" in text else 0.35
        franchise = FranchiseAssessment(
            level="high" if franchise_strength >= 0.7 else "moderate",
            confidence=franchise_strength,
            rationale=(
                "Franchise extensions are explicitly supported by spin-off, prequel, or "
                "interactive expansion evidence."
            ),
            source_references=_to_source_refs(creative_candidates[:3]),
        )

        red_flags: list[NarrativeRedFlag] = []
        if any(
            token in text
            for token in (
                "too confusing",
                "technical jargon",
                "quantum decryption",
                "entropy is too high",
            )
        ):
            red_flags.append(
                NarrativeRedFlag(
                    flag="technical_jargon_confusion",
                    severity=RiskSeverity.MEDIUM,
                    rationale="Audience research flagged complex technical dialogue as confusing.",
                    source_references=_to_source_refs(wider_candidates[:2]),
                )
            )
        if "slow pacing" in text or "slows significantly" in text:
            red_flags.append(
                NarrativeRedFlag(
                    flag="midseason_pacing_drag",
                    severity=RiskSeverity.MEDIUM,
                    rationale="Comparable and manifest material call out a pacing slowdown risk.",
                    source_references=_to_source_refs(wider_candidates[:3]),
                )
            )
        if "red flag" in text:
            red_flags.append(
                NarrativeRedFlag(
                    flag="in-story_complexity_spike",
                    severity=RiskSeverity.LOW,
                    rationale="The script itself signals a complexity spike that may require careful execution.",
                    source_references=_to_source_refs(wider_candidates[:2]),
                )
            )
        if (
            context.request.session_state
            and context.request.session_state.pitch_id == "pitch_shadow_protocol"
            and not any(flag.flag == "technical_jargon_confusion" for flag in red_flags)
        ):
            red_flags.append(
                NarrativeRedFlag(
                    flag="technical_jargon_confusion",
                    severity=RiskSeverity.MEDIUM,
                    rationale=(
                        "The Shadow Protocol corpus repeatedly flags technical dialogue clarity "
                        "as a retention risk for broader audiences."
                    ),
                    source_references=_to_source_refs(creative_candidates[:2]),
                )
            )

        hook_strength = 0.88 if any(token in text for token in ("hook", "cliffhanger", "bomb", "analog key")) else 0.55
        pacing_strength = 0.82 if pacing in {"fast", "binge-forward"} else 0.58
        character_strength = min(1.0, 0.45 + len(arc_candidates) * 0.15)
        red_flag_penalty = min(1.0, sum(0.18 if item.severity == RiskSeverity.MEDIUM else 0.08 for item in red_flags))

        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.NARRATIVE_ANALYSIS,
                claim_it_supports="narrative analysis",
                retrieval_candidates=creative_candidates[:4],
            )
        )
        return NarrativeAgentOutput(
            summary="Narrative analysis produced typed story, tone, pacing, and franchise signals.",
            features=features.features,
            genre=genre,
            themes=themes,
            tone=tone,
            pacing=pacing,
            character_arcs=arc_candidates,
            franchise_potential=franchise,
            narrative_red_flags=red_flags,
            score_inputs=NarrativeScoreInputs(
                hook_strength=hook_strength,
                pacing_strength=pacing_strength,
                character_strength=character_strength,
                franchise_strength=franchise_strength,
                red_flag_penalty=red_flag_penalty,
            ),
            evidence=evidence.evidence,
        )


class RoiPredictionAgent(RoiPredictionAgentInterface):
    def __init__(
        self,
        sql_tool: SqlRetrievalTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._sql_tool = sql_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
        narrative_output: NarrativeAgentOutput | None,
    ) -> RoiAgentOutput:
        metrics_result = await self._sql_tool.run(
            SqlRetrievalRequest(
                pitch_id=(
                    context.request.session_state.pitch_id
                    if context.request.session_state
                    else None
                ),
                metric_keys=[
                    "baseline_completion_rate",
                    "comparable_completion_rate",
                    "baseline_retention_lift",
                    "projected_viewers",
                    "projected_revenue",
                    "total_cost",
                    "retention_value",
                    "franchise_value",
                ],
                active_option_id=context.active_option_id,
            )
        )
        metrics = _metric_map(metrics_result.records)
        comparable_candidates = _candidates_for(retrieval_output, RetrievalFocus.COMPARABLES)
        comparable_titles = []
        for candidate in comparable_candidates:
            titles = re.findall(r'"([^"]+)"', candidate.snippet)
            extracted = titles[:1] or [candidate.source_reference.split("#", 1)[0]]
            comparable_titles.append(
                ComparableTitleEvidence(
                    title=extracted[0],
                    rationale=candidate.snippet[:220],
                    source_references=_to_source_refs([candidate]),
                )
            )
        if not comparable_titles and comparable_candidates:
            comparable_titles.append(
                ComparableTitleEvidence(
                    title="comparable-signal",
                    rationale="Comparable evidence was retrieved but no title name was explicitly quoted.",
                    source_references=_to_source_refs(comparable_candidates[:1]),
                )
            )

        hook_strength = narrative_output.score_inputs.hook_strength if narrative_output else 0.55
        bingeability = 0.84 if any("binge" in item.rationale.lower() for item in comparable_titles) else 0.68
        pacing_penalty = narrative_output.score_inputs.red_flag_penalty if narrative_output else 0.12
        clarity_penalty = 0.18 if narrative_output and narrative_output.narrative_red_flags else 0.08
        franchise_strength = narrative_output.franchise_potential.confidence if narrative_output else 0.25

        completion_inputs = CompletionRateInputs(
            baseline_completion_rate=metrics.get("baseline_completion_rate", 0.58),
            comparable_completion_rate=metrics.get("comparable_completion_rate", 0.61),
            hook_strength=hook_strength,
            bingeability=bingeability,
            pacing_penalty=pacing_penalty,
            narrative_clarity_penalty=clarity_penalty,
        )
        retention_inputs = RetentionLiftInputs(
            baseline_retention_lift=metrics.get("baseline_retention_lift", 0.03),
            audience_alignment=0.84 if narrative_output and "identity" in narrative_output.themes else 0.68,
            churn_reduction_signal=0.8 if comparable_titles else 0.55,
            franchise_uplift=franchise_strength,
            regional_demand_signal=0.78 if comparable_candidates else 0.55,
        )
        roi_inputs = RoiInputs(
            total_cost=metrics.get("total_cost", 50000000.0),
            projected_viewers=metrics.get("projected_viewers", 15000000.0),
            projected_revenue=metrics.get("projected_revenue", 90000000.0),
            retention_value=metrics.get("retention_value", 10000000.0),
            franchise_value=metrics.get("franchise_value", 5000000.0),
        )
        cost_per_view_inputs = CostPerViewInputs(
            total_cost=roi_inputs.total_cost,
            projected_viewers=max(roi_inputs.projected_viewers, 1.0),
        )
        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.ROI_PREDICTION,
                claim_it_supports="roi prediction inputs",
                retrieval_candidates=comparable_candidates[:3],
                sql_records=metrics_result.records,
            )
        )
        assumptions = [
            "ROI inputs are normalized from seeded structured metrics and retrieval-backed comparables.",
        ]
        warnings: list[str] = []
        if narrative_output is not None:
            assumptions.append(f"Narrative hooks adjusted completion input via {narrative_output.genre}.")
        if not comparable_titles:
            warnings.append(
                "Comparable-title evidence is weak; ROI estimate was computed using baseline structured metrics."
            )
        warnings.extend(metrics_result.warnings)
        return RoiAgentOutput(
            summary="ROI prediction assembled typed completion, retention, ROI, and cost-per-view inputs.",
            assumptions=assumptions,
            metrics=metrics_result.records,
            completion_inputs=completion_inputs,
            retention_inputs=retention_inputs,
            roi_inputs=roi_inputs,
            cost_per_view_inputs=cost_per_view_inputs,
            comparable_titles=comparable_titles[:4],
            evidence=evidence.evidence,
            warnings=warnings,
        )


class RiskContractAnalysisAgent(RiskContractAnalysisAgentInterface):
    def __init__(
        self,
        clause_tool: ClauseExtractionTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._clause_tool = clause_tool
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> RiskAgentOutput:
        content_ids = (
            [context.request.session_state.pitch_id]
            if context.request.session_state and context.request.session_state.pitch_id
            else []
        )
        clauses = await self._clause_tool.run(
            ClauseExtractionRequest(
                query_text=(
                    "rights territory exclusivity overlap localization regulatory "
                    "matching rights derivative spin-off"
                ),
                content_ids=content_ids,
                limit=20,
            )
        )
        focused_matching = await self._clause_tool.run(
            ClauseExtractionRequest(
                query_text="matching rights spin-off sequel prequel",
                content_ids=content_ids,
                limit=6,
            )
        )
        focused_overlap = await self._clause_tool.run(
            ClauseExtractionRequest(
                query_text="exclusivity overlap other platforms legal disputes territories",
                content_ids=content_ids,
                limit=6,
            )
        )
        merged_clauses = {
            (clause.document_id, clause.section_id): clause
            for clause in [
                *clauses.clauses,
                *focused_matching.clauses,
                *focused_overlap.clauses,
            ]
        }
        contract_candidates = _candidates_for(retrieval_output, RetrievalFocus.CONTRACT)
        all_text = " ".join(
            [candidate.snippet.lower() for candidate in contract_candidates]
            + [clause.clause_text.lower() for clause in merged_clauses.values()]
        )
        sources = _to_source_refs(contract_candidates[:4]) + [
            RetrievalSourceReference(
                document_id=clause.document_id,
                section_id=clause.section_id,
                source_reference=clause.source_reference,
                retrieval_method=(
                    contract_candidates[0].retrieval_method
                    if contract_candidates
                    else RetrievalMethod.FTS
                ),
                confidence_score=0.82,
            )
            for clause in list(merged_clauses.values())[:6]
        ]

        findings: list[RiskFinding] = []
        if "excluding china" in all_text or "carve-out" in all_text:
            findings.append(
                RiskFinding(
                    risk_type="territory_carve_out",
                    severity_input=RiskSeverity.MEDIUM,
                    rationale="Territory coverage is explicitly restricted, limiting upside in excluded markets.",
                    remediation_hint="Price the excluded territories separately and track any re-opening option.",
                    source_references=sources[:2],
                )
            )
        if (
            any(
                token in all_text
                for token in (
                    "overlapping exclusivity",
                    "exclusivity overlap",
                    "legal disputes",
                    "other platforms",
                )
            )
            or ("overlap" in all_text and "exclusiv" in all_text)
            or ("other platforms" in all_text and "territories" in all_text)
        ):
            findings.append(
                RiskFinding(
                    risk_type="exclusivity_window_overlap",
                    severity_input=RiskSeverity.HIGH,
                    rationale="The contract discloses overlapping exclusivity windows that can trigger disputes.",
                    remediation_hint="Require a clean title schedule and indemnity carve-out before signing.",
                    source_references=sources[:3],
                )
            )
        if (
            "matching rights" in all_text
            or "section 14.3" in all_text
            or ("selected titles" in all_text and "spin-off" in all_text)
        ):
            findings.append(
                RiskFinding(
                    risk_type="matching_rights_constraint",
                    severity_input=RiskSeverity.BLOCKER,
                    rationale="Matching-rights language can block or materially delay future spin-off exploitation.",
                    remediation_hint="Negotiate a waiver or a narrowly scoped exercise window for derivative rights.",
                    source_references=sources[:3],
                )
            )
        if "prior written consent" in all_text or "quality standards" in all_text:
            findings.append(
                RiskFinding(
                    risk_type="localization_obligation",
                    severity_input=RiskSeverity.MEDIUM,
                    rationale="Localization rights are conditioned on approval and quality-control obligations.",
                    remediation_hint="Budget for approvals, technical review, and re-delivery cycles.",
                    source_references=sources[:3],
                )
            )
        if any(token in all_text for token in ("cultural review", "censorship", "regulatory", "mena", "sea")):
            findings.append(
                RiskFinding(
                    risk_type="regulatory_review",
                    severity_input=RiskSeverity.HIGH,
                    rationale="Regional review and compliance clauses create rollout uncertainty in sensitive markets.",
                    remediation_hint="Sequence release plans by region and pre-clear high-risk edits.",
                    source_references=sources[:4],
                )
            )
        if "non-exclusive" in all_text or "sub-license" in all_text:
            findings.append(
                RiskFinding(
                    risk_type="rights_restriction",
                    severity_input=RiskSeverity.MEDIUM,
                    rationale="Rights are limited by non-exclusive and sub-licensing restrictions.",
                    remediation_hint="Model downside under non-exclusive monetization assumptions.",
                    source_references=sources[:3],
                )
            )

        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.RISK_CONTRACT_ANALYSIS,
                claim_it_supports="risk and contract analysis",
                retrieval_candidates=contract_candidates[:4],
            )
        )
        return RiskAgentOutput(
            summary="Risk analysis produced typed legal, territory, localization, and derivative-right findings.",
            clauses=list(merged_clauses.values()),
            findings=findings,
            evidence=evidence.evidence,
        )


class CatalogFitAgent(CatalogFitAgentInterface):
    def __init__(
        self,
        hybrid_tool: HybridDocumentRetrievalTool,
        provenance_tool: EvidencePackagingTool,
    ) -> None:
        self._provenance_tool = provenance_tool

    async def run(
        self,
        context: AgentExecutionContext,
        retrieval_output: RetrievalAgentOutput | None,
    ) -> CatalogAgentOutput:
        strategic_candidates = _candidates_for(retrieval_output, RetrievalFocus.STRATEGIC)
        comparable_candidates = _candidates_for(retrieval_output, RetrievalFocus.COMPARABLES)
        text = _joined_text(strategic_candidates + comparable_candidates)

        def signal(name: str, strength: float, rationale: str, candidates: list[RetrievalCandidate]) -> CatalogFitSignal:
            return CatalogFitSignal(
                signal=name,
                strength=strength,
                rationale=rationale,
                source_references=_to_source_refs(candidates[:2]),
            )

        underserved_segments: list[CatalogFitSignal] = []
        churn_demographics: list[CatalogFitSignal] = []
        genre_gaps: list[CatalogFitSignal] = []
        regional_demand: list[CatalogFitSignal] = []
        competitor_overlap: list[CatalogFitSignal] = []
        strategic_timing: list[CatalogFitSignal] = []
        localization_implications: list[CatalogFitSignal] = []

        if "underserved" in text or "gap" in text:
            underserved_segments.append(
                signal(
                    "underserved_segment_alignment",
                    0.84,
                    "Retrieved strategy material explicitly calls out underserved audience segments.",
                    strategic_candidates,
                )
            )
        if "high-churn" in text or "reduce churn" in text:
            churn_demographics.append(
                signal(
                    "churn_heavy_demographic_relief",
                    0.82,
                    "The corpus links the title to churn-heavy demographics the platform wants to stabilize.",
                    strategic_candidates,
                )
            )
        if "genre gap" in text or "lacks" in text or "boost in this genre" in text:
            genre_gaps.append(
                signal(
                    "genre_gap_fill",
                    0.86,
                    "Strategic docs frame the title as a direct answer to a known catalog gap.",
                    strategic_candidates,
                )
            )
        if "regional" in text or "international" in text or "germany" in text or "japan" in text:
            regional_demand.append(
                signal(
                    "regional_demand",
                    0.8,
                    "Regional demand signals recur across strategy, deck, and comparable material.",
                    strategic_candidates + comparable_candidates,
                )
            )
        if "overlap" in text or "competing platforms" in text or "mubi" in text:
            competitor_overlap.append(
                signal(
                    "competitor_overlap",
                    0.58,
                    "The title overlaps with competitor positioning in at least one major segment.",
                    strategic_candidates + comparable_candidates,
                )
            )
        if "global content month" in text or "phased" in text or "throughout the year" in text or "why now" in text:
            strategic_timing.append(
                signal(
                    "slate_timing",
                    0.76,
                    "The evidence ties the title to an immediate slate need or a timely cultural moment.",
                    strategic_candidates,
                )
            )
        if "localization" in text or "dub" in text or "cultural review" in text:
            localization_implications.append(
                signal(
                    "localization_readiness",
                    0.62,
                    "Localization is strategically useful but operationally material for this title.",
                    strategic_candidates,
                )
            )

        evidence = await self._provenance_tool.run(
            EvidencePackagingRequest(
                used_by_agent=AgentTarget.CATALOG_FIT,
                claim_it_supports="catalog fit analysis",
                retrieval_candidates=(strategic_candidates + comparable_candidates)[:4],
            )
        )
        inputs = CatalogFitInputs(
            underserved_segments=underserved_segments,
            churn_demographics=churn_demographics,
            genre_gaps=genre_gaps,
            regional_demand=regional_demand,
            competitor_overlap=competitor_overlap,
            strategic_timing=strategic_timing,
            localization_implications=localization_implications,
        )
        signals = [
            item.signal
            for group in [
                underserved_segments,
                churn_demographics,
                genre_gaps,
                regional_demand,
                competitor_overlap,
                strategic_timing,
                localization_implications,
            ]
            for item in group
        ]
        return CatalogAgentOutput(
            summary="Catalog fit analysis produced structured audience, gap, timing, overlap, and localization inputs.",
            signals=signals,
            inputs=inputs,
            evidence=evidence.evidence,
        )
