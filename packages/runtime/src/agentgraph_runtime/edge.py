"""Edges and conditional routing between nodes.

An `Edge` is a static transition: when node A finishes, go to node B.
A `ConditionalEdge` evaluates a function on the current state and returns
the next node name (or `END`).
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from pydantic import BaseModel, Field

from agentgraph_runtime.state import GraphState


class Edge(BaseModel):
    """A static edge `from -> to`."""

    source: str
    target: str
    description: str = ""

    model_config = {"arbitrary_types_allowed": True}


RouteFn = Callable[[GraphState], "str | Awaitable[str]"]


class ConditionalEdge(BaseModel):
    """A dynamic edge whose target is decided by `route(state)`."""

    source: str
    route: Annotated[Any, Field(exclude=True)]
    description: str = ""

    model_config = {"arbitrary_types_allowed": True}

    async def decide(self, state: GraphState) -> str:
        result = self.route(state)
        if inspect.isawaitable(result):
            result = await result
        return str(result)
