"""`Runner`: a convenience wrapper around `Runtime` for one-liner runs.

By default a `Runner` uses durable storage (SQLite, or whatever
`AG_STORAGE_URL` points to) for both checkpoints and the audit log, so runs
survive restarts and every action is recorded. Pass `storage_url="memory://"`
for ephemeral runs (used by the test suite).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentgraph_core.audit import AuditLog
from agentgraph_core.rbac import Principal
from agentgraph_core.storage import audit_log_from_url, default_storage_url
from agentgraph_runtime.checkpoint import CheckpointStore, checkpoint_store_from_url
from agentgraph_runtime.graph import Graph
from agentgraph_runtime.runtime import Runtime, RuntimeConfig
from agentgraph_runtime.state import GraphState


@dataclass(slots=True)
class RunResult:
    """The outcome of a `Runner.run(...)`."""

    state: GraphState
    output: Any
    cost_usd: float
    tokens: int
    finished: bool
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.state.run.run_id,
            "thread_id": self.state.run.thread_id,
            "output": self.output,
            "cost_usd": self.cost_usd,
            "tokens": self.tokens,
            "finished": self.finished,
            "error": self.error,
        }


class Runner:
    """A preconfigured `Runtime` with durable storage by default.

    Vertical packs construct a `Runner` (via their `Service`) and expose it
    through their API. Storage is selected from `storage_url` (default:
    `AG_STORAGE_URL` or a SQLite file under the platform data directory).
    """

    def __init__(
        self,
        *,
        checkpoint_store: CheckpointStore | None = None,
        audit_log: AuditLog | None = None,
        principal: Principal | None = None,
        storage_url: str | None = None,
    ) -> None:
        url = storage_url or default_storage_url()
        self.config = RuntimeConfig(
            checkpoint_store=checkpoint_store or checkpoint_store_from_url(url),
            audit_log=audit_log or audit_log_from_url(url),
            principal=principal,
        )

    def runtime(self) -> Runtime:
        return Runtime(self.config)

    async def arun(self, graph: Graph, **kwargs: Any) -> RunResult:
        state = await self.runtime().run(graph, **kwargs)
        return _to_result(state)

    def run(self, graph: Graph, **kwargs: Any) -> RunResult:
        import asyncio

        return asyncio.run(self.arun(graph, **kwargs))


def _to_result(state: GraphState) -> RunResult:
    return RunResult(
        state=state,
        output=state.values.get("agent_output") or state.values.get("output"),
        cost_usd=float(state.values.get("total_cost_usd", 0.0) or 0.0),
        tokens=int(state.values.get("total_tokens", 0) or 0),
        finished=state.finished,
        error=state.error,
    )
