from __future__ import annotations

import random

import pytest
from score import benchmark_outcome, capability_outcome, derive_top_set, verdict


def test_confidence_boundaries():
    assert benchmark_outcome(0.101, 0.2, 0.1) == "lead"
    assert benchmark_outcome(-0.1, 0.1, 0.1) == "tie"
    assert benchmark_outcome(-0.099, 0.5, 0.1) == "non-inferior"
    assert benchmark_outcome(-0.1, 0.5, 0.1) == "failure"


def test_nonbenchmarkable_equivalence_requires_independent_every_must_have():
    base = [{"product_meets": True, "evidence_tier": "integration-contract", "status": "verified"}]
    assert capability_outcome(base) == "equivalent"
    assert capability_outcome([{**base[0], "evidence_tier": "official-documentation"}]) == "failure"
    assert capability_outcome([{**base[0], "status": "restricted"}]) == "unknown"


def test_no_pre_run_selection_and_deterministic_post_hash():
    dim = {"dimension_id": "quality", "direction": "higher", "delta": 0.1}
    results = [
        {
            "result_id": "r2",
            "product_id": "b",
            "eligible": True,
            "locked": True,
            "status": "measured",
            "value": 0.91,
            "ci_low": 0.89,
            "ci_high": 0.93,
        },
        {
            "result_id": "r1",
            "product_id": "a",
            "eligible": True,
            "locked": True,
            "status": "measured",
            "value": 1.0,
            "ci_low": 0.95,
            "ci_high": 1.05,
        },
        {
            "result_id": "r3",
            "product_id": "c",
            "eligible": True,
            "locked": True,
            "status": "unknown",
        },
    ]
    with pytest.raises(ValueError):
        derive_top_set(dim, results, phase="pre-measurement")
    one = derive_top_set(dim, results, phase="post-measurement")
    random.shuffle(results)
    two = derive_top_set(dim, results, phase="post-measurement")
    assert (
        one == two and one["top_comparators"] == ["a", "b"] and one["unknown_candidates"] == ["c"]
    )


def test_every_comparator_gate_and_decisive_unknown():
    d = {
        "dimension_id": "d",
        "classification": "critical",
        "top_set_frozen": True,
        "comparisons": [
            {"competitor_id": "a", "outcome": "lead"},
            {"competitor_id": "b", "outcome": "tie"},
        ],
    }
    assert verdict([d], [{"gate_id": "g", "status": "pass"}])["label"] == "SOTA"
    d["comparisons"][1]["outcome"] = "failure"
    assert verdict([d], [{"gate_id": "g", "status": "pass"}])["label"] == "Not Yet SOTA"
    d["comparisons"][1]["outcome"] = "unknown"
    r = verdict([d], [{"gate_id": "g", "status": "pass"}])
    assert r["label"] == "Not Yet SOTA" and r["inconclusive_evidence"] == ["d vs b"]
