from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .evaluation import RecommendationConfig


class EvalBehavior(StrEnum):
    DETERMINISTIC_PASS = "DETERMINISTIC_PASS"
    UNCERTAINTY = "UNCERTAINTY"
    WARNING = "WARNING"
    PASS_FAIL = "PASS_FAIL"


class RequiredEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_reference: str | None = None
    section_id: str | None = None


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fixture_id: str
    query: str
    pitch_id: str | None = None
    request_context: dict[str, Any] = Field(default_factory=dict)
    
    # Ground Truth
    golden_answer: str | None = None
    expected_key_risks: list[str] = Field(default_factory=list)
    expected_roi_facts: list[str] = Field(default_factory=list)
    required_evidence: list[RequiredEvidence] = Field(default_factory=list)
    
    # Behavior validation
    behavior: EvalBehavior = EvalBehavior.DETERMINISTIC_PASS
    is_adversarial: bool = False
    
    # Sensitivity & Multi-turn
    config_perturbations: list[RecommendationConfig] = Field(default_factory=list)
    multi_turn_sequence: list[str] = Field(default_factory=list)


class JudgeScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=1, le=5)
    rationale: str


class CaseEvalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_id: str
    passed: bool
    faithfulness: JudgeScore | None = None
    helpfulness: JudgeScore | None = None
    recall_at_5: float | None = None
    precision_at_5: float | None = None
    failure_reasons: list[str] = Field(default_factory=list)
    
    # For summary aggregation
    is_adversarial: bool = False
    has_multi_turn: bool = False
    
    # For sensitivity/multi-turn details
    sensitivity_results: list[dict[str, Any]] = Field(default_factory=list)
    multi_turn_results: list[dict[str, Any]] = Field(default_factory=list)


class EvalSuiteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cases: int
    pass_rate: float
    avg_faithfulness: float | None = None
    avg_helpfulness: float | None = None
    recall_at_5: float | None = None
    precision_at_5: float | None = None
    adversarial_pass_rate: float | None = None
    multiturn_consistency_pass_rate: float | None = None
    config_sensitivity_summary: dict[str, Any] = Field(default_factory=dict)
    
    per_case_details: list[CaseEvalResult] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=datetime.now)
