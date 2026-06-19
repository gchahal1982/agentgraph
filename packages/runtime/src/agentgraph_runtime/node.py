"""Node primitives.

A `Node` is a unit of work. The runtime calls `Node.run(state) -> NodeResult`
and uses `NodeResult.next` to decide where to go next (or `goto` for
explicit routing, or `END` to finish).
"""
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from agentgraph_core.errors import GraphError
from agentgraph_core.types import JSONValue
from pydantic import BaseModel, Field

from agentgraph_runtime.state import GraphState

END: str = "__end__"


@dataclass(slots=True)
class NodeResult:
    """The outcome of executing a single node."""

    # The default next node, used by the runtime unless the result
    # carries an explicit `goto`.
    next: str | None = None
    # Optional override: a list of node names to attempt, in order.
    goto: list[str] = field(default_factory=list)
    # Side-channel values to merge into the graph state.
    updates: dict[str, JSONValue] = field(default_factory=dict)
    # Append messages to the conversation.
    messages: list = field(default_factory=list)
    # Signal an error. The runtime converts this to a run.error audit event.
    error: str | None = None
    # When True, the graph is finished.
    end: bool = False

    def to_next(self, default: str | None) -> str | None:
        if self.end:
            return END
        if self.goto:
            return self.goto[0]
        return self.next or default


NodeHandler = Callable[[GraphState], "NodeResult | Awaitable[NodeResult]"]


class Node(BaseModel):
    """A named unit of work in the graph."""

    name: str
    description: str = ""
    handler: Annotated[Any, Field(exclude=True)]
    # Optional policy: enforce a permission requirement before the node runs.
    requires: str | None = None  # Permission name, e.g. "data.read.phi"
    # If True, node failures don't terminate the run; they set state.error
    # and the runtime continues to the next node (or to `on_error`).
    swallow_errors: bool = False
    on_error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    async def run(self, state: GraphState) -> NodeResult:
        try:
            result = self.handler(state)
            if inspect.isawaitable(result):
                result = await result
        except Exception as e:
            if self.swallow_errors:
                return NodeResult(
                    error=f"{type(e).__name__}: {e}",
                    next=self.on_error,
                )
            raise
        if not isinstance(result, NodeResult):
            raise GraphError(
                f"Node {self.name!r} must return NodeResult, got {type(result).__name__}"
            )
        return result


def node(name: str | None = None, *, requires: str | None = None, swallow_errors: bool = False, on_error: str | None = None) -> Callable[[NodeHandler], Node]:
    """Decorator that wraps a function as a `Node`.

    Usage::

        @node("qualify_lead")
        async def qualify_lead(state: GraphState) -> NodeResult:
            ...
    """

    def _wrap(fn: NodeHandler) -> Node:
        n = name or fn.__name__
        return Node(
            name=n,
            description=inspect.getdoc(fn) or "",
            handler=fn,
            requires=requires,
            swallow_errors=swallow_errors,
            on_error=on_error,
        )

    return _wrap
