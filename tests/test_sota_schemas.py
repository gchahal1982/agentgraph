from __future__ import annotations

import json
import shutil
from pathlib import Path

from verify import ROOT_SCHEMAS, schema_registry, validate_document, verify

ROOT = Path(__file__).parents[1]


def test_all_closed_draft_202012_schemas_and_portfolio_validate():
    schemas, registry = schema_registry(ROOT / "docs/sota/evidence/schema")
    assert set(ROOT_SCHEMAS.values()) <= set(schemas)
    assert all(
        x["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        and x.get("additionalProperties") is False
        for n, x in schemas.items()
        if n != "portfolio.schema.json"
    )
    report = verify(ROOT, strict=True, offline=True)
    assert report.ok and report.mode == "portfolio-skeleton" and not report.schema_errors


def test_date_only_and_unknown_fields_are_rejected(tmp_path):
    schemas, registry = schema_registry(ROOT / "docs/sota/evidence/schema")
    data = {
        "schema_version": "1.0.0",
        "run_id": "r",
        "phase": "review",
        "started_at": "2026-07-17",
        "completed_at": "2026-07-17T00:00:00Z",
        "tested_sha": "a" * 40,
        "schema_bundle_sha256": "b" * 64,
        "protocol_sha256": "c" * 64,
        "environment": "test",
        "results": [],
        "surprise": True,
    }
    p = tmp_path / "run.json"
    p.write_text(json.dumps(data))
    errors = validate_document(p, schemas["run.schema.json"], registry)
    assert any("does not match" in x for x in errors) and any(
        "Additional properties" in x for x in errors
    )


def test_missing_product_roots_are_structured_errors_not_crashes(tmp_path):
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    (tmp_path / "docs/sota/evidence/scope.json").write_text("{}")
    report = verify(tmp_path, strict=True, offline=True)
    assert not report.ok and any("missing evidence root" in x for x in report.schema_errors)
