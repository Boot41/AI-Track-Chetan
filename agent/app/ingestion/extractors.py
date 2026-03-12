from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from app.schemas.ingestion import DocumentClassification, DocumentType, SectionRecord


class ContractFactExtractor:
    def extract(
        self,
        classification: DocumentClassification,
        sections: list[SectionRecord],
    ) -> list[dict[str, object]]:
        if classification.doc_type != DocumentType.CONTRACT:
            return []

        facts: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for section in sections:
            text = f"{section.title or ''}: {section.content}".strip(": ")
            lowered = text.lower()
            candidates: list[tuple[str, str, str, str | None, float]] = []

            if "exclusive right" in lowered or "non-exclusive right" in lowered:
                rights_scope = "exclusive" if "exclusive right" in lowered else "non-exclusive"
                candidates.append(
                    ("license", "rights_granted", rights_scope, None, 0.93)
                )
            if "worldwide" in lowered or "territory" in lowered or "excluding china" in lowered:
                candidates.append(("license", "territory_scope", text, None, 0.92))
            if "global exclusivity" in lowered or "exclusive window" in lowered:
                candidates.append(("license", "exclusivity_window", text, None, 0.91))
            if "matching rights" in lowered:
                candidates.append(("license", "matching_rights", text, None, 0.95))
            if "spin-off" in lowered or "prequel" in lowered or "derivative works" in lowered:
                candidates.append(("license", "derivative_rights_limit", text, None, 0.88))
            if "dubbing" in lowered or "subtitling" in lowered or "localized" in lowered:
                candidates.append(("license", "localization_obligation", text, None, 0.9))
            if "initial term" in lowered:
                candidates.append(("license", "term_length", text, None, 0.94))
            if "renewal option" in lowered or "renew" in lowered:
                candidates.append(("license", "renewal_constraint", text, None, 0.88))

            for subject, predicate, object_value, qualifier, confidence in candidates:
                signature = (section.section_id, predicate)
                if signature in seen:
                    continue
                seen.add(signature)
                facts.append(
                    {
                        "fact_id": str(uuid5(NAMESPACE_URL, f"{section.section_id}:{predicate}")),
                        "document_id": section.document_id,
                        "section_id": section.section_id,
                        "subject": subject,
                        "predicate": predicate,
                        "object_value": object_value,
                        "qualifier": qualifier,
                        "source_text": text[:500],
                        "confidence": confidence,
                        "extracted_by": "contract_clause_extractor",
                    }
                )
        return facts


class DocumentRiskExtractor:
    _RULES: tuple[tuple[str, str, str, str, float], ...] = (
        ("matching rights", "matching_rights", "HIGH", "Matching-rights clause limits sequel control.", 0.92),
        ("conditional approval", "conditional_approval", "HIGH", "Conditional approval creates release risk.", 0.9),
        ("cultural review", "regulatory_review", "HIGH", "Regional cultural review may delay distribution.", 0.88),
        ("exclusivity overlap", "exclusivity_overlap", "HIGH", "Overlapping exclusivity windows may trigger disputes.", 0.95),
        ("sub-licensing", "sub_licensing_limit", "HIGH", "Sub-licensing limitations reduce exploitation flexibility.", 0.91),
        ("localization", "localization_risk", "MEDIUM", "Localization quality obligations increase execution risk.", 0.8),
        ("regulatory uncertainty", "regulatory_uncertainty", "HIGH", "Regulatory uncertainty can constrain rollout.", 0.84),
        ("censorship", "censorship_risk", "HIGH", "Censorship concerns may require edits or exclusions.", 0.86),
    )

    def extract(
        self,
        classification: DocumentClassification,
        sections: list[SectionRecord],
    ) -> list[dict[str, object]]:
        if classification.doc_type not in {DocumentType.CONTRACT, DocumentType.REPORT, DocumentType.MEMO}:
            return []

        risks: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for section in sections:
            lowered = f"{section.title or ''}: {section.content}".lower()
            for needle, risk_type, severity, summary, confidence in self._RULES:
                if needle not in lowered:
                    continue
                signature = (section.section_id, risk_type)
                if signature in seen:
                    continue
                seen.add(signature)
                risks.append(
                    {
                        "id": str(uuid5(NAMESPACE_URL, f"{section.section_id}:{risk_type}")),
                        "document_id": section.document_id,
                        "section_id": section.section_id,
                        "risk_type": risk_type,
                        "severity": severity,
                        "summary": summary,
                        "mitigation": "Review source section and confirm exploitability constraints.",
                        "source_text": f"{section.title or ''}: {section.content}"[:500],
                        "status": "open",
                        "confidence": confidence,
                    }
                )
        return risks
