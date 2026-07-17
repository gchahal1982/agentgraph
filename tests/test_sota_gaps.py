from __future__ import annotations

import json
from pathlib import Path

from render import GAP_COLUMNS, render_gap_table
from verify import schema_registry, validate_document

DIMS = [
    "architecture",
    "APIs",
    "auth/security",
    "reliability",
    "performance",
    "observability",
    "DX",
    "deployment/operations",
    "connectors/integrations",
    "agent UX",
    "human-in-loop",
    "evals",
    "domain workflows",
]


def test_all_dimensions_and_exact_minimum_columns(tmp_path):
    gaps = []
    for i, d in enumerate(DIMS):
        gaps.append(
            {
                "gap_id": f"g{i}",
                "product_id": "p",
                "repository": "o/r",
                "title": d,
                "dimension": d,
                "classification": "meaningful",
                "criterion_ids": ["c"],
                "claim_ids": ["cl"],
                "source_ids": ["s"],
                "run_ids": [],
                "current_state": "current evidence",
                "sota_target": "frontier evidence",
                "baseline_measurement": "baseline",
                "disposition": "gap",
                "gap": "measured gap",
                "implementation_path": ["module.py: close behavior"],
                "acceptance_metric": "metric",
                "acceptance_command": "pytest",
                "target_threshold": "pass",
                "effort": ["S", "M", "L", "XL"][i % 4],
                "priority": f"P{i % 4}",
                "owner_role": "maintainer",
                "dependencies": [],
                "approval_gates": [],
                "status": "observed",
                "target_branch": "sota/gap",
                "target_pr": "pending",
                "rollback_plan": "revert",
            }
        )
    data = {"schema_version": "1.0.0", "product_id": "p", "gaps": gaps}
    p = tmp_path / "gaps.json"
    p.write_text(json.dumps(data))
    schemas, reg = schema_registry(Path(__file__).parents[1] / "docs/sota/evidence/schema")
    assert validate_document(p, schemas["gap.schema.json"], reg) == []
    table = render_gap_table(gaps)
    assert tuple(x.strip() for x in table.splitlines()[0].strip("|").split("|")) == GAP_COLUMNS
    assert all(d in table for d in DIMS)
