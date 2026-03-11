from __future__ import annotations

from agent.app.schemas.evaluation import RiskFinding, RiskScore, RiskSeverity

_RISK_ORDER = {
    RiskSeverity.LOW: 0,
    RiskSeverity.MEDIUM: 1,
    RiskSeverity.HIGH: 2,
    RiskSeverity.BLOCKER: 3,
}

_SAFETY_SCORE = {
    RiskSeverity.LOW: 85.0,
    RiskSeverity.MEDIUM: 65.0,
    RiskSeverity.HIGH: 35.0,
    RiskSeverity.BLOCKER: 5.0,
}


class RiskSeverityScorer:
    def score(self, findings: list[RiskFinding]) -> RiskScore:
        if not findings:
            return RiskScore(
                overall_severity=RiskSeverity.LOW,
                safety_score=92.0,
                rationale="No material contract or regulatory risks were surfaced.",
            )

        overall = max(findings, key=lambda item: _RISK_ORDER[item.severity_input]).severity_input
        average_safety = sum(_SAFETY_SCORE[item.severity_input] for item in findings) / len(findings)
        if overall == RiskSeverity.BLOCKER:
            safety_score = min(average_safety, _SAFETY_SCORE[RiskSeverity.BLOCKER])
        elif overall == RiskSeverity.HIGH:
            safety_score = min(average_safety, 45.0)
        else:
            safety_score = average_safety
        return RiskScore(
            overall_severity=overall,
            safety_score=round(max(0.0, min(100.0, safety_score)), 2),
            rationale="Aggregated the surfaced findings by worst-case severity with a conservative cap.",
        )
