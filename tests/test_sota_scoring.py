from __future__ import annotations

from decimal import Decimal

from score import ANCHORS, MULTIPLIERS, display, score_criteria, sensitivity, strongest_evidence


def criterion(subs, weight=1):
    return {"criterion_id": "c", "weight": weight, "subcriteria": subs}


def evidence(anchor, tier, **kw):
    return {"evidence_id": tier, "raw_anchor": anchor, "tier": tier, **kw}


def test_every_anchor_and_tier():
    assert set(ANCHORS) == set(range(5))
    assert set(MULTIPLIERS.values()) == {
        Decimal("1"),
        Decimal(".85"),
        Decimal(".65"),
        Decimal(".45"),
        Decimal(".20"),
        Decimal("0"),
    }
    for anchor in ANCHORS:
        result = score_criteria(
            [criterion([{"subcriterion_id": "s", "evidence": [evidence(anchor, "live")]}])]
        )
        assert result["overall"] == Decimal(anchor) * 25


def test_strongest_tier_and_partial_agentflow_rule():
    chosen = strongest_evidence(
        [
            evidence(4, "official-documentation"),
            evidence(3, "integration-contract", proves_full_claim=False, partial_anchor=2),
            evidence(2, "deterministic-unit"),
        ]
    )
    assert (
        chosen["tier"] == "integration-contract"
        and chosen["raw_anchor"] == 2
        and chosen["adjusted"] == Decimal("1.70")
    )


def test_na_denominator_unresolved_and_half_up_full_precision():
    subs = [
        {"subcriterion_id": "a", "evidence": [evidence(3, "deterministic-unit")]},
        {
            "subcriterion_id": "na",
            "state": "not-applicable",
            "applicability_approved": True,
            "applicability_justification": "pre-frozen",
        },
        {"subcriterion_id": "u", "state": "unknown"},
    ]
    result = score_criteria([criterion(subs)])
    assert (
        result["overall"] == Decimal("24.375")
        and result["display_overall"] == "24.4"
        and result["unresolved"] == ["u"]
    )
    assert display(Decimal("84.95")) == "85.0"


def test_sensitivity_weight_and_leave_one_out():
    criteria = [
        criterion([{"subcriterion_id": "a", "evidence": [evidence(4, "live")]}], 1),
        {
            "criterion_id": "d",
            "weight": 1,
            "subcriteria": [{"subcriterion_id": "b", "evidence": [evidence(0, "absent")]}],
        },
    ]
    report = sensitivity(criteria)
    assert set(report["weight_perturbations"]["c"]) == {
        "minus_25_percent",
        "plus_25_percent",
    } and set(report["leave_one_out"]) == {"a", "b"}
