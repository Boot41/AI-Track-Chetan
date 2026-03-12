from __future__ import annotations

import pytest
from .metrics import calculate_precision_at_k, calculate_recall_at_k
from ..schemas.eval_runner import RequiredEvidence


def test_recall_at_k_computes_correctly():
    required = [
        RequiredEvidence(source_reference="Ref 1"),
        RequiredEvidence(section_id="sec-2"),
    ]
    retrieved = [
        {"source_reference": "Ref 1", "section_id": "sec-1"},
        {"source_reference": "Ref 3", "section_id": "sec-3"},
        {"source_reference": "Ref 2", "section_id": "sec-2"},
    ]
    
    # Recall@3: Both found
    assert calculate_recall_at_k(retrieved, required, k=3) == 1.0
    
    # Recall@1: Only Ref 1 found
    assert calculate_recall_at_k(retrieved, required, k=1) == 0.5
    
    # Recall@2: Still only Ref 1 found (sec-2 is at index 2, so index 0 and 1 are checked)
    assert calculate_recall_at_k(retrieved, required, k=2) == 0.5


def test_precision_at_k_computes_correctly():
    retrieved = [
        {"section_id": "sec-1"},
        {"section_id": "sec-2"},
        {"section_id": "sec-3"},
    ]
    relevant = ["sec-1", "sec-3"]
    
    # Precision@1: (sec-1) -> 1/1
    assert calculate_precision_at_k(retrieved, relevant, k=1) == 1.0
    
    # Precision@2: (sec-1, sec-2) -> 1/2
    assert calculate_precision_at_k(retrieved, relevant, k=2) == 0.5
    
    # Precision@3: (sec-1, sec-2, sec-3) -> 2/3
    assert calculate_precision_at_k(retrieved, relevant, k=3) == pytest.approx(0.6666666666666666)
