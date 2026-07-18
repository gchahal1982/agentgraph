"""Regression tests for the local SOTA benchmark collector."""
from __future__ import annotations

import pytest

from scripts.sota_collect import collect


@pytest.mark.asyncio
async def test_collect_emits_every_declared_suite() -> None:
    manifest = {
        "benchmark_id": "test-benchmark",
        "protocol_version": "1.0.0",
        "minimum_timed_samples": 1,
        "seed": 7,
        "suites": [
            {
                "id": "linear-runtime",
                "node_counts": [1],
                "warmup_samples": 0,
                "invariants": [],
            },
            {
                "id": "security-contract",
                "invariants": [
                    "authentication",
                    "redaction",
                    "generic errors",
                ],
            },
        ],
    }

    report = await collect(manifest)

    assert [result["suite_id"] for result in report["results"]] == [
        "linear-runtime",
        "security-contract",
    ]
    assert all(result["failures"] == 0 for result in report["results"])


@pytest.mark.asyncio
async def test_collect_rejects_unsupported_suite() -> None:
    manifest = {
        "benchmark_id": "test-benchmark",
        "protocol_version": "1.0.0",
        "minimum_timed_samples": 1,
        "seed": 7,
        "suites": [{"id": "unknown"}],
    }

    with pytest.raises(ValueError, match="Unsupported benchmark suite: unknown"):
        await collect(manifest)
