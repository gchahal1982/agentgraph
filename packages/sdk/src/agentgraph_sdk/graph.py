"""`Graph`: thin wrapper around the runtime's `GraphBuilder`."""
from __future__ import annotations

from typing import Any

from agentgraph_core.types import JSONValue
from agentgraph_runtime.graph import Graph as RuntimeGraph
from agentgraph_runtime.graph import GraphBuilder as RuntimeBuilder
from agentgraph_runtime.node import END, Node
from agentgraph_runtime.runtime import Runtime

from agentgraph_sdk.agent import Agent


class Graph:
    """A user-facing multi-node graph.

    Example::

        g = Graph("sales_pipeline")
        g.add_agent(sales_agent, entrypoint=True)
        g.add_node(review_node)
        g.add_edge(sales_agent.node.name, review_node.name)
        g.add_edge(review_node.name, END)
    """

    def __init__(self, name: str = "graph") -> None:
        self.name = name
        self._builder = RuntimeBuilder(name=name)
        self._agents: dict[str, Agent] = {}

    # --- builders ---

    def add_agent(self, agent: Agent, *, entrypoint: bool = False) -> Graph:
        self._agents[agent.node.spec.name] = agent
        self._builder.add_node(agent.node.node)
        if entrypoint:
            self._builder.set_entrypoint(agent.node.spec.name)
        return self

    def add_node(self, n: Node) -> Graph:
        self._builder.add_node(n)
        return self

    def add_edge(self, source: str, target: str) -> Graph:
        self._builder.add_edge(source, target)
        return self

    def add_conditional_edge(self, source: str, route) -> Graph:
        self._builder.add_conditional_edge(source, route)
        return self

    def set_entrypoint(self, name: str) -> Graph:
        self._builder.set_entrypoint(name)
        return self

    def compile(self) -> RuntimeGraph:
        return self._builder.compile()

    # --- execution helpers ---

    def run(
        self,
        *,
        input: dict[str, JSONValue] | None = None,
        runtime: Runtime | None = None,
    ) -> Any:
        import asyncio

        compiled = self.compile()
        rt = runtime or Runtime()
        return asyncio.get_event_loop().run_until_complete(
            rt.run(compiled, input=input)
        )

    async def arun(
        self,
        *,
        input: dict[str, JSONValue] | None = None,
        runtime: Runtime | None = None,
    ) -> Any:
        compiled = self.compile()
        rt = runtime or Runtime()
        return await rt.run(compiled, input=input)


def END_NODE() -> str:  # noqa: N802 - convenient alias
    return END
