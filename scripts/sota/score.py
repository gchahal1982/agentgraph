"""Frozen, deterministic SOTA scoring and comparator adjudication rules."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from _common import digest, read_json, write_json

ANCHORS = {
    0: "absent/contradicted",
    1: "interface, claim, or manual prototype",
    2: "functional happy path with deterministic unit/contract evidence",
    3: "representative integration/failure/security evidence",
    4: "independently reproducible frontier-equivalent or leading behavior",
}
MULTIPLIERS = {
    "independently-reproduced": Decimal("1.00"),
    "live": Decimal("1.00"),
    "integration-contract": Decimal("0.85"),
    "deterministic-unit": Decimal("0.65"),
    "code-inspection": Decimal("0.45"),
    "official-documentation": Decimal("0.20"),
    "absent": Decimal("0"),
}
UNRESOLVED = {"unknown", "conflicting", "restricted", "stale", "non-comparable"}
PASSING_OUTCOMES = {"lead", "tie", "non-inferior", "equivalent"}


def display(value: Decimal | float | int) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def strongest_evidence(items: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    admissible = [item for item in items if item.get("status", "verified") not in UNRESOLVED]
    if not admissible:
        return None

    # Partial evidence lowers the anchor before the strongest tier is applied once.
    def adjusted(item: dict[str, Any]) -> tuple[Decimal, Decimal, str]:
        raw = Decimal(str(item["raw_anchor"]))
        if not item.get("proves_full_claim", True):
            raw = min(raw, Decimal(str(item.get("partial_anchor", max(0, int(raw) - 1)))))
        tier = MULTIPLIERS[item["tier"]]
        return raw * tier, tier, str(item.get("evidence_id", ""))

    chosen = max(admissible, key=lambda item: (MULTIPLIERS[item["tier"]], adjusted(item)))
    result = dict(chosen)
    if not chosen.get("proves_full_claim", True):
        result["raw_anchor"] = min(
            chosen["raw_anchor"], chosen.get("partial_anchor", max(0, chosen["raw_anchor"] - 1))
        )
    result["adjusted"] = Decimal(str(result["raw_anchor"])) * MULTIPLIERS[result["tier"]]
    return result


def score_criteria(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    if not criteria or sum(Decimal(str(item["weight"])) for item in criteria) <= 0:
        raise ValueError("criteria require positive weights")
    results: list[dict[str, Any]] = []
    unresolved: list[str] = []
    weighted = Decimal("0")
    total_weight = sum(Decimal(str(item["weight"])) for item in criteria)
    for criterion in criteria:
        numerator = Decimal("0")
        denominator = Decimal("0")
        for sub in criterion["subcriteria"]:
            state = sub.get("state", "scored")
            if state == "not-applicable":
                if not sub.get("applicability_approved") or not sub.get(
                    "applicability_justification"
                ):
                    unresolved.append(sub["subcriterion_id"])
                continue
            denominator += Decimal("4")
            if state in UNRESOLVED:
                unresolved.append(sub["subcriterion_id"])
                continue
            selected = strongest_evidence(sub.get("evidence", []))
            if selected is None:
                unresolved.append(sub["subcriterion_id"])
            else:
                numerator += selected["adjusted"]
        percentage = numerator / denominator * Decimal("100") if denominator else Decimal("0")
        weight = Decimal(str(criterion["weight"]))
        weighted += percentage * weight / total_weight
        results.append(
            {
                "criterion_id": criterion["criterion_id"],
                "percentage": percentage,
                "display_percentage": display(percentage),
                "weight": weight,
            }
        )
    return {
        "criteria": results,
        "overall": weighted,
        "display_overall": display(weighted),
        "unresolved": sorted(unresolved),
        "complete": not unresolved,
    }


def sensitivity(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    base = score_criteria(criteria)["overall"]
    perturbations: dict[str, dict[str, str]] = {}
    for index, criterion in enumerate(criteria):
        values: dict[str, str] = {}
        for label, factor in (
            ("minus_25_percent", Decimal("0.75")),
            ("plus_25_percent", Decimal("1.25")),
        ):
            changed = [dict(item) for item in criteria]
            changed[index] = dict(
                changed[index], weight=Decimal(str(changed[index]["weight"])) * factor
            )
            values[label] = str(score_criteria(changed)["overall"])
        perturbations[criterion["criterion_id"]] = values
    leave_one_out: dict[str, str] = {}
    for criterion in criteria:
        for sub in criterion["subcriteria"]:
            changed = []
            for candidate in criteria:
                copy = dict(candidate)
                copy["subcriteria"] = [
                    x
                    for x in candidate["subcriteria"]
                    if x["subcriterion_id"] != sub["subcriterion_id"]
                ]
                changed.append(copy)
            leave_one_out[sub["subcriterion_id"]] = str(score_criteria(changed)["overall"])
    return {
        "base": str(base),
        "weight_perturbations": perturbations,
        "leave_one_out": leave_one_out,
    }


def derive_top_set(
    dimension: dict[str, Any], results: list[dict[str, Any]], *, phase: str
) -> dict[str, Any]:
    if phase != "post-measurement":
        raise ValueError(
            "top comparators cannot be selected before matched measurements are locked"
        )
    eligible = [item for item in results if item.get("eligible") and item.get("locked")]
    known = [item for item in eligible if item.get("status") == "measured"]
    unknown = sorted(item["product_id"] for item in eligible if item.get("status") != "measured")
    selected: list[str] = []
    if known:
        direction = dimension["direction"]
        best = (
            max(item["value"] for item in known)
            if direction == "higher"
            else min(item["value"] for item in known)
        )
        delta = dimension["delta"]
        for item in known:
            within = abs(item["value"] - best) <= delta
            uncertainty_best = item["ci_low"] <= best <= item["ci_high"]
            capability = item.get("capability_leader", False) and dimension.get(
                "non_benchmarkable", False
            )
            if within or uncertainty_best or capability:
                selected.append(item["product_id"])
    selected.sort()
    artifact = {
        "dimension_id": dimension["dimension_id"],
        "rule_version": "1.0.0",
        "matched_result_ids": sorted(item["result_id"] for item in eligible),
        "top_comparators": selected,
        "unknown_candidates": unknown,
    }
    artifact["sha256"] = digest(artifact)
    return artifact


def benchmark_outcome(ci_low: float, ci_high: float, delta: float) -> str:
    if ci_low > delta:
        return "lead"
    if ci_low >= -delta and ci_high <= delta:
        return "tie"
    if ci_low > -delta:
        return "non-inferior"
    return "failure"


def capability_outcome(must_haves: list[dict[str, Any]]) -> str:
    if any(item.get("status") in UNRESOLVED for item in must_haves):
        return "unknown"
    if any(
        not item.get("product_meets") or item.get("evidence_tier") == "official-documentation"
        for item in must_haves
    ):
        return "failure"
    return "equivalent"


def verdict(dimensions: list[dict[str, Any]], hard_gates: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    inconclusive: list[str] = []
    for dimension in dimensions:
        if dimension["classification"] == "supporting":
            continue
        if not dimension.get("top_set_frozen"):
            blockers.append(f"{dimension['dimension_id']}: top set is not frozen")
        for comparison in dimension.get("comparisons", []):
            status = comparison["outcome"]
            label = f"{dimension['dimension_id']} vs {comparison['competitor_id']}"
            if status in UNRESOLVED or status == "unknown":
                if comparison.get("decisive", True):
                    inconclusive.append(label)
            elif status not in PASSING_OUTCOMES:
                blockers.append(label)
    for gate in hard_gates:
        if gate.get("status") != "pass":
            blockers.append(f"hard gate: {gate['gate_id']}")
    eligible = not blockers and not inconclusive and bool(dimensions)
    return {
        "label": "SOTA" if eligible else "Not Yet SOTA",
        "inconclusive_evidence": sorted(inconclusive),
        "blockers": sorted(blockers),
        "eligible": eligible,
    }


def select_head_to_head(
    candidates: list[dict[str, Any]], minimum: int = 3, maximum: int = 5
) -> list[str]:
    if len(candidates) < minimum:
        raise ValueError(f"at least {minimum} comparator candidates are required")
    ordered = sorted(
        candidates,
        key=lambda item: (
            -item["top_dimension_count"],
            -item["weighted_criterion_coverage"],
            -item["workflow_relevance"],
            -item["evidence_freshness"],
            item["product_id"],
        ),
    )
    return [item["product_id"] for item in ordered[:maximum]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str)
    parser.add_argument("--output")
    args = parser.parse_args()
    source = read_json(__import__("pathlib").Path(args.input))
    result = score_criteria(source["criteria"])
    serializable = {
        **result,
        "overall": str(result["overall"]),
        "criteria": [
            {**x, "percentage": str(x["percentage"]), "weight": str(x["weight"])}
            for x in result["criteria"]
        ],
    }
    if args.output:
        write_json(__import__("pathlib").Path(args.output), serializable)
    else:
        print(__import__("json").dumps(serializable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
