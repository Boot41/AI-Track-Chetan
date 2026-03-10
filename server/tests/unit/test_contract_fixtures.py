from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.contracts import DocumentFactContract, PublicResponseContract, QueryClassification

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_FIXTURE_DIR = REPO_ROOT / "agent" / "app" / "evals" / "fixtures" / "phase0"
CLIENT_FIXTURE_DIR = REPO_ROOT / "client" / "src" / "fixtures" / "phase0"
SERVER_FIXTURE_DIR = REPO_ROOT / "server" / "app" / "fixtures" / "public_responses"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "filename",
    [
        "original_series_evaluation.json",
        "acquisition_evaluation.json",
        "comparison_evaluation.json",
    ],
)
def test_primary_eval_fixtures_have_valid_classification(filename: str) -> None:
    payload = _load_json(AGENT_FIXTURE_DIR / filename)
    assert isinstance(payload, dict)
    QueryClassification.model_validate(payload["expected_classification"])


def test_followup_routing_fixture_cases_validate_against_contract() -> None:
    payload = _load_json(AGENT_FIXTURE_DIR / "followup_routing_cases.json")
    assert isinstance(payload, list)
    assert len(payload) >= 5
    for case in payload:
        QueryClassification.model_validate(case["expected_classification"])


def test_contract_risk_clause_fixture_contains_valid_document_facts() -> None:
    payload = _load_json(AGENT_FIXTURE_DIR / "contract_risk_clause_cases.json")
    assert isinstance(payload, list)
    for case in payload:
        for fact in case["expected_facts"]:
            DocumentFactContract.model_validate(fact)


@pytest.mark.parametrize(
    "filename",
    [
        "standard_evaluation_response.json",
        "comparison_response.json",
        "followup_response.json",
    ],
)
def test_frontend_phase0_response_fixtures_match_public_contract(filename: str) -> None:
    payload = _load_json(CLIENT_FIXTURE_DIR / filename)
    response = PublicResponseContract.model_validate(payload)
    assert set(response.meta.model_dump()) == {"warnings", "confidence", "review_required"}


@pytest.mark.parametrize(
    "filename",
    [
        "standard_evaluation_response.json",
        "comparison_response.json",
        "followup_response.json",
    ],
)
def test_backend_stub_response_fixtures_match_public_contract(filename: str) -> None:
    payload = _load_json(SERVER_FIXTURE_DIR / filename)
    response = PublicResponseContract.model_validate(payload)
    assert set(response.meta.model_dump()) == {"warnings", "confidence", "review_required"}
