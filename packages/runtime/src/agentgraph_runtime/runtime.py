"""The runtime: execute compiled graphs.

The runtime is the engine that drives a graph: it picks the next node,
executes it, takes a checkpoint, and continues. It can be suspended
(via `Handoff`) and resumed later from the last checkpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from agentgraph_core.audit import (
    AuditAction,
    AuditEvent,
    AuditLog,
    InMemoryAuditLog,
)
from agentgraph_core.errors import GraphError, PolicyError
from agentgraph_core.observability import span
from agentgraph_core.rbac import Permission, Principal
from agentgraph_core.types import JSONValue

from agentgraph_runtime.checkpoint import (
    Checkpoint,
    CheckpointStore,
    InMemoryCheckpointStore,
)
from agentgraph_runtime.edge import ConditionalEdge
from agentgraph_runtime.graph import Graph
from agentgraph_runtime.handoff import HandoffRouter
from agentgraph_runtime.node import END, Node, NodeResult
from agentgraph_runtime.state import GraphState

_log = structlog.get_logger("agentgraph.runtime")


@dataclass(slots=True)
class RuntimeConfig:
    """Configuration for a runtime instance."""

    checkpoint_store: CheckpointStore = field(default_factory=InMemoryCheckpointStore)
    audit_log: AuditLog = field(default_factory=InMemoryAuditLog)
    handoff_router: HandoffRouter = field(default_factory=HandoffRouter)
    principal: Principal | None = None
    max_total_steps: int = 256


class Runtime:
    """Drives a compiled graph."""

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()

    async def run(
        self,
        graph: Graph,
        *,
        input: dict[str, JSONValue] | None = None,
        thread_id: str | None = None,
        principal: Principal | None = None,
    ) -> GraphState:
        """Execute a graph from start to finish or until a handoff.

        Returns the final `GraphState`. Use `Runtime.resume(thread_id)` to
        continue a run that was paused for handoff.
        """
        state = GraphState()
        state.run.input = input or {}
        state.run.thread_id = thread_id or state.run.thread_id
        principal = principal or self.config.principal
        state.run.principal_id = principal.id if principal else None
        state.current_node = graph.entrypoint

        await self._audit(
            AuditAction.RUN_START,
            actor=graph.entrypoint,
            state=state,
            payload={"graph": graph.entrypoint, "input": state.run.input},
        )

        return await self._execute(graph, state, principal)

    async def resume(self, graph: Graph, thread_id: str) -> GraphState:
        """Resume the most recent run for `thread_id` from its last checkpoint."""
        cps = await self.config.checkpoint_store.list_for_thread(thread_id)
        if not cps:
            raise GraphError(f"No checkpoint for thread {thread_id!r}")
        last = cps[-1]
        state = GraphState.from_checkpoint_dict(last.state)
        principal = self.config.principal
        return await self._execute(graph, state, principal)

    # --- internals ---

    async def _execute(
        self, graph: Graph, state: GraphState, principal: Principal | None
    ) -> GraphState:
        steps = 0
        while not state.finished and steps < self.config.max_total_steps:
            steps += 1
            current = state.current_node
            if current is None or current == END:
                state.finished = True
                break

            node = graph.nodes.get(current)
            if node is None:
                raise GraphError(f"Unknown node {current!r} in graph")

            await self._enforce_policy(node, principal, state)

            with span(
                "node",
                node=node.name,
                run_id=state.run.run_id,
                thread_id=state.run.thread_id,
            ) as s:
                try:
                    result: NodeResult = await node.run(state)
                except Exception as exc:
                    error_type = type(exc).__name__
                    s.fail(error_type)
                    state.error = error_type
                    await self._audit(
                        AuditAction.ERROR,
                        actor=node.name,
                        state=state,
                        payload={"error_type": error_type},
                    )
                    raise
                s.set("updates", list(result.updates.keys()))
                s.set("next", result.next)

            # Apply updates and messages.
            for k, v in result.updates.items():
                state.values[k] = v
            for m in result.messages:
                state.add_message(m)

            if result.error:
                await self._audit(
                    AuditAction.ERROR,
                    actor=node.name,
                    state=state,
                    payload={"error": "Node execution reported an error"},
                )
                # Swallowed errors are handled control flow. Never persist raw
                # exception text; an unhandled NodeResult error is represented
                # by a stable public-safe marker.
                if not node.swallow_errors:
                    state.error = "Node execution reported an error"

            # Determine the next node.
            nxt: str | None
            if result.end:
                nxt = END
            elif result.goto:
                nxt = result.goto[0]
            elif result.next is not None:
                nxt = result.next
            else:
                # Try a static edge.
                succs = graph.successors_of(node.name)
                nxt = succs[0] if succs else None
                # If no static edge, try a conditional edge.
                if nxt is None:
                    cond: ConditionalEdge | None = graph.conditional_for(node.name)
                    if cond is not None:
                        nxt = await cond.decide(state)
                    else:
                        # No successors; this is an end.
                        nxt = END

            state.next_node = nxt
            state.current_node = nxt
            state.finished = nxt == END

            # Take a checkpoint after every executed node, including terminal nodes.
            await self.config.checkpoint_store.save(
                Checkpoint(
                    run_id=state.run.run_id,
                    thread_id=state.run.thread_id,
                    node=node.name,
                    state=state.to_checkpoint_dict(),
                )
            )

        if not state.finished and steps >= self.config.max_total_steps:
            state.error = f"max_total_steps={self.config.max_total_steps} exceeded"
            await self._audit(
                AuditAction.ERROR,
                actor=state.current_node or "runtime",
                state=state,
                payload={"error": state.error},
            )

        await self._audit(
            AuditAction.RUN_END,
            actor=state.current_node or "runtime",
            state=state,
            payload={"finished": state.finished, "cost_usd": state.values.get("total_cost_usd", 0.0)},
        )
        return state

    async def _enforce_policy(
        self,
        node: Node,
        principal: Principal | None,
        state: GraphState,
    ) -> None:
        if not node.requires:
            return
        if principal is None:
            raise PolicyError(f"Node {node.name!r} requires permission {node.requires!r} but no principal")
        try:
            perm = Permission(node.requires)
        except ValueError as e:
            raise GraphError(f"Node {node.name!r} declared unknown permission {node.requires!r}") from e
        if not principal.has(perm):
            raise PolicyError(
                f"Principal {principal.id!r} lacks permission {perm.value!r} required by {node.name!r}"
            )
        await self._audit(
            AuditAction.POLICY_DECISION,
            actor=node.name,
            state=state,
            payload={"permission": perm.value, "principal": principal.id, "decision": "allow"},
        )

    async def _audit(
        self,
        action: AuditAction,
        *,
        actor: str,
        state: GraphState,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self.config.audit_log.write(
            AuditEvent(
                run_id=state.run.run_id,
                thread_id=state.run.thread_id,
                principal_id=state.run.principal_id,
                action=action,
                actor=actor,
                payload=payload or {},
            )
        )
