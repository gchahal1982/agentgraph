"""Validate a SOTA evidence tree without importing AgentGraph packages."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from _common import duplicate_ids, read_json, semantic_walk
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT_SCHEMAS = {
    "scope.json": "scope.schema.json",
    "criteria.json": "criteria.schema.json",
    "competitors.json": "competitor.schema.json",
    "sources.json": "source.schema.json",
    "claims.json": "claim.schema.json",
    "gaps.json": "gap.schema.json",
    "context.json": "context.schema.json",
    "verdict.json": "verdict.schema.json",
}
PORTFOLIO_SCHEMAS = {
    "products.json": "portfolio.schema.json",
    "index-config.json": "portfolio.schema.json",
    "open-studio-context.json": "portfolio.schema.json",
}


@dataclass
class Report:
    schema_errors: list[str] = field(default_factory=list)
    unresolved_blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    verdict_eligible: bool = False
    mode: str = "portfolio-skeleton"

    @property
    def ok(self) -> bool:
        return not self.schema_errors and not self.unresolved_blockers


def schema_registry(schema_dir: Path) -> tuple[dict[str, Any], Registry[Any]]:
    schemas: dict[str, Any] = {}
    registry = Registry()
    for path in sorted(schema_dir.glob("*.schema.json")):
        schema = read_json(path)
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return schemas, registry


def validate_document(path: Path, schema: dict[str, Any], registry: Registry[Any]) -> list[str]:
    data = read_json(path)
    validator = Draft202012Validator(schema, registry=registry)
    errors = [
        f"{path}: {'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]
    errors.extend(f"{path}: {error}" for error in semantic_walk(data))
    errors.extend(f"{path}: {error}" for error in duplicate_ids(data))
    return errors


def _reference_checks(evidence_dir: Path, report: Report) -> None:
    loaded = {name: read_json(evidence_dir / name) for name in ROOT_SCHEMAS}
    source_ids = {item["source_id"] for item in loaded["sources.json"]["sources"]}
    claim_ids = {item["claim_id"] for item in loaded["claims.json"]["claims"]}
    criterion_ids = {item["criterion_id"] for item in loaded["criteria.json"]["criteria"]}
    run_ids: set[str] = set()
    for path in (
        (evidence_dir / "runs").glob("*/*.json") if (evidence_dir / "runs").exists() else []
    ):
        value = read_json(path)
        if isinstance(value, dict) and isinstance(value.get("run_id"), str):
            run_ids.add(value["run_id"])
    for claim in loaded["claims.json"]["claims"]:
        for source_id in claim["source_ids"]:
            if source_id not in source_ids:
                report.unresolved_blockers.append(
                    f"claim {claim['claim_id']} has dangling source {source_id}"
                )
    for gap in loaded["gaps.json"]["gaps"]:
        for criterion_id in gap["criterion_ids"]:
            if criterion_id not in criterion_ids:
                report.unresolved_blockers.append(
                    f"gap {gap['gap_id']} has dangling criterion {criterion_id}"
                )
        for claim_id in gap["claim_ids"]:
            if claim_id not in claim_ids:
                report.unresolved_blockers.append(
                    f"gap {gap['gap_id']} has dangling claim {claim_id}"
                )
        for run_id in gap["run_ids"]:
            if run_id not in run_ids:
                report.unresolved_blockers.append(f"gap {gap['gap_id']} has dangling run {run_id}")
    expected = set(loaded["scope.json"]["required_dimensions"])
    covered = {item["dimension"] for item in loaded["gaps.json"]["gaps"]}
    if expected != covered:
        report.unresolved_blockers.append(
            f"gap coverage mismatch: missing={sorted(expected - covered)}, extra={sorted(covered - expected)}"
        )
    verdict = loaded["verdict.json"]
    report.verdict_eligible = verdict["label"] == "SOTA" and verdict.get("eligible", False)
    if verdict["label"] == "SOTA" and (
        verdict.get("blockers") or verdict.get("inconclusive_evidence")
    ):
        report.unresolved_blockers.append("SOTA verdict contains blockers or inconclusive evidence")


def verify(root: Path, strict: bool = False, offline: bool = False) -> Report:
    del offline  # All verifier behavior is local; retained as an explicit policy flag.
    report = Report()
    schema_dir = root / "docs/sota/evidence/schema"
    portfolio_dir = root / "docs/sota/evidence/portfolio"
    try:
        schemas, registry = schema_registry(schema_dir)
    except Exception as exc:
        report.schema_errors.append(f"schema bundle: {exc}")
        return report
    for filename, schema_name in PORTFOLIO_SCHEMAS.items():
        path = portfolio_dir / filename
        if not path.exists():
            report.schema_errors.append(f"missing portfolio root: {path}")
            continue
        report.schema_errors.extend(validate_document(path, schemas[schema_name], registry))
    evidence_dir = root / "docs/sota/evidence"
    existing = [name for name in ROOT_SCHEMAS if (evidence_dir / name).exists()]
    if existing:
        report.mode = "product-evidence"
        for filename, schema_name in ROOT_SCHEMAS.items():
            path = evidence_dir / filename
            if not path.exists():
                report.schema_errors.append(f"missing evidence root: {path}")
                continue
            report.schema_errors.extend(validate_document(path, schemas[schema_name], registry))
        if len(existing) == len(ROOT_SCHEMAS) and not report.schema_errors:
            _reference_checks(evidence_dir, report)
    else:
        report.warnings.append(
            "portfolio skeleton mode: product evidence roots are intentionally owned by Task 3"
        )
    if strict and report.warnings and report.mode != "portfolio-skeleton":
        report.unresolved_blockers.extend(report.warnings)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = verify(args.root.resolve(), strict=args.strict, offline=args.offline)
    payload = asdict(report) | {"ok": report.ok}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
