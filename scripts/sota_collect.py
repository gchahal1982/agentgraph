"""Run the deterministic local AgentGraph runtime benchmark.

The fixture and bootstrap resampling are seeded. Wall-clock values naturally
vary by host; invariant outcomes and report shape are deterministic.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import math
import os
import platform
import random
import resource
import statistics
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from agentgraph_core.audit import AuditAction, InMemoryAuditLog
from agentgraph_runtime.checkpoint import InMemoryCheckpointStore
from agentgraph_runtime.graph import GraphBuilder
from agentgraph_runtime.node import Node, NodeResult
from agentgraph_runtime.runtime import Runtime, RuntimeConfig
from agentgraph_runtime.state import GraphState
from agentgraph_server.app import AppState, create_app
from agentgraph_server.registry import RegisteredAgent
from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[1]


def _node(index: int) -> Node:
    async def execute(state: GraphState) -> NodeResult:
        state.values["executed"] = int(state.values.get("executed", 0)) + 1
        return NodeResult(end=index == int(state.run.input["node_count"]) - 1)

    return Node(name=f"node-{index}", handler=execute)


def _graph(node_count: int):
    nodes = [_node(index) for index in range(node_count)]
    builder = GraphBuilder().add_nodes(*nodes).set_entrypoint(nodes[0].name)
    for current, following in itertools.pairwise(nodes):
        builder.add_edge(current.name, following.name)
    return builder.compile()


async def _sample(node_count: int) -> tuple[float, bool, int, int]:
    checkpoints = InMemoryCheckpointStore()
    audit = InMemoryAuditLog()
    runtime = Runtime(RuntimeConfig(checkpoint_store=checkpoints, audit_log=audit))
    graph = _graph(node_count)
    started = time.perf_counter_ns()
    state = await runtime.run(graph, input={"node_count": node_count})
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    saved = await checkpoints.list_for_thread(state.run.thread_id)
    events = await audit.query(run_id=state.run.run_id)
    actions = {event.action for event in events}
    valid = (
        state.finished
        and state.error is None
        and state.values.get("executed") == node_count
        and len(saved) == node_count
        and {AuditAction.RUN_START, AuditAction.RUN_END} <= actions
    )
    return elapsed_ms, valid, len(saved), len(events)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _bootstrap_median_ci(values: list[float], seed: int, samples: int = 2_000) -> list[float]:
    rng = random.Random(seed)
    medians = [statistics.median(rng.choices(values, k=len(values))) for _ in range(samples)]
    return [round(_percentile(medians, 0.025), 6), round(_percentile(medians, 0.975), 6)]


async def _collect_linear_suite(
    suite: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    warmups = int(suite["warmup_samples"])
    samples = int(manifest["minimum_timed_samples"])
    cases = []
    for node_count in suite["node_counts"]:
        for _ in range(warmups):
            await _sample(node_count)
        measurements = [await _sample(node_count) for _ in range(samples)]
        latencies = [item[0] for item in measurements]
        cases.append(
            {
                "node_count": node_count,
                "samples": samples,
                "failures": sum(not item[1] for item in measurements),
                "checkpoint_count": measurements[-1][2],
                "audit_event_count": measurements[-1][3],
                "latency_ms": {
                    "p50": round(statistics.median(latencies), 6),
                    "p95": round(_percentile(latencies, 0.95), 6),
                    "p99": round(_percentile(latencies, 0.99), 6),
                    "median_bootstrap_95_ci": _bootstrap_median_ci(
                        latencies, int(manifest["seed"]) + node_count
                    ),
                },
                "throughput_runs_per_second": round(1000 / statistics.mean(latencies), 6),
            }
        )
    return {"suite_id": suite["id"], "failures": sum(c["failures"] for c in cases), "cases": cases}


async def _collect_security_suite(suite: dict[str, Any]) -> dict[str, Any]:
    secret = "benchmark-secret-value"
    store = InMemoryCheckpointStore()
    audit = InMemoryAuditLog()
    with patch.dict(
        os.environ,
        {"AG_API_KEY": "benchmark-key", "AG_ALLOW_INSECURE_NO_AUTH": "0"},
    ):
        state = AppState(storage_url="memory://")
    state.checkpoints = store
    state.audit = audit
    state.registry.register_sync(
        RegisteredAgent("security-probe", "security probe", "benchmark", _graph(1))
    )
    checks: list[dict[str, Any]] = []
    with TestClient(create_app(state, register_verticals=False), raise_server_exceptions=False) as client:
        checks.append(
            {
                "invariant": suite["invariants"][0],
                "passed": client.get("/agents").status_code == 401,
            }
        )
        headers = {"Authorization": "Bearer benchmark-key"}
        thread_id = client.post("/threads", headers=headers).json()["thread_id"]
        response = client.post(
            f"/threads/{thread_id}/run",
            headers=headers,
            json={"agent": "security-probe", "input": {"token": secret, "node_count": 1}},
        )
        events = await audit.query(thread_id=thread_id)
        checks.append(
            {
                "invariant": suite["invariants"][1],
                "passed": response.status_code == 200
                and secret not in json.dumps([event.model_dump(mode="json") for event in events]),
            }
        )
        broken = _graph(1)

        async def fail(_state: GraphState) -> NodeResult:
            raise RuntimeError(secret)

        broken.nodes["node-0"] = Node(name="node-0", handler=fail)
        state.registry.register_sync(
            RegisteredAgent("broken-probe", "broken probe", "benchmark", broken)
        )
        failed = client.post(
            f"/threads/{thread_id}/run",
            headers=headers,
            json={"agent": "broken-probe", "input": {"node_count": 1}},
        )
        checks.append(
            {
                "invariant": suite["invariants"][2],
                "passed": failed.status_code == 500 and secret not in failed.text,
            }
        )
    return {
        "suite_id": suite["id"],
        "failures": sum(not check["passed"] for check in checks),
        "checks": checks,
    }


async def collect(manifest: dict[str, Any]) -> dict[str, Any]:
    results = []
    collectors = {
        "linear-runtime": lambda suite: _collect_linear_suite(suite, manifest),
        "security-contract": _collect_security_suite,
    }
    for suite in manifest["suites"]:
        try:
            collector = collectors[suite["id"]]
        except KeyError as exc:
            raise ValueError(f"Unsupported benchmark suite: {suite['id']}") from exc
        results.append(await collector(suite))
    return {
        "benchmark_id": manifest["benchmark_id"],
        "protocol_version": manifest["protocol_version"],
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "resource_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "results": results,
        "limitations": [
            "Local synthetic benchmark; no competitor adapter or external service is measured.",
            "Single-process in-memory stores isolate runtime overhead and do not prove crash recovery.",
            "Wall-clock latency is host-specific and is not a SOTA comparison."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "benchmarks/manifest.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = asyncio.run(collect(manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return int(any(item["failures"] for item in report["results"]))


if __name__ == "__main__":
    raise SystemExit(main())
