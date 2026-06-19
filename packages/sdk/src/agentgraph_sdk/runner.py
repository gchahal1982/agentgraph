"""`Runner`: a convenience wrapper around `Runtime` for one-liner runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentgraph_core.audit import AuditLog, InMemoryAuditLog
from agentgraph_core.rbac import Principal
from agentgraph_runtime.checkpoint import CheckpointStore, InMemoryCheckpointStore
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
    """A preconfigured `Runtime`.

    Vertical packs construct a `Runner` with their default audit log,
    checkpoint store, and handoff channels, then expose it for use in
    their examples and APIs.
    """

    def __init__(
        self,
        *,
        checkpoint_store: CheckpointStore | None = None,
        audit_log: AuditLog | None = None,
        principal: Principal | None = None,
    ) -> None:
        self.config = RuntimeConfig(
            checkpoint_store=checkpoint_store or InMemoryCheckpointStore(),
            audit_log=audit_log or InMemoryAuditLog(),
            principal=principal,
        )

    def runtime(self) -> Runtime:
        return Runtime(self.config)

    async def arun(self, graph: Graph, **kwargs) -> RunResult:
        state = await self.runtime().run(graph, **kwargs)
        return _to_result(state)

    def run(self, graph: Graph, **kwargs) -> RunResult:
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.arun(graph, **kwargs))


def _to_result(state: GraphState) -> RunResult:
    return RunResult(
        state=state,
        output=state.values.get("agent_output") or state.values.get("output"),
        cost_usd=float(state.values.get("total_cost_usd", 0.0) or 0.0),
        tokens=int(state.values.get("total_tokens", 0) or 0),
        finished=state.finished,
        error=state.error,
    )
