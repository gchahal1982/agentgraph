"""Graph: a directed graph of nodes and edges.

Use the `GraphBuilder` fluent API to construct graphs, then `graph.compile()`
to produce a `Graph` ready for the runtime.
"""

from __future__ import annotations

from collections.abc import Callable

from agentgraph_core.errors import GraphError
from pydantic import BaseModel, Field

from agentgraph_runtime.edge import ConditionalEdge, Edge
from agentgraph_runtime.node import END, Node


class Graph(BaseModel):
    """Compiled graph ready for execution.

    The runtime walks nodes, applying static edges or invoking conditional
    edges to find the next node. The graph is validated at compile time
    to surface structural errors before deployment.
    """

    entrypoint: str
    nodes: dict[str, Node] = Field(default_factory=dict)
    static_edges: list[Edge] = Field(default_factory=list)
    conditional_edges: list[ConditionalEdge] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def validate_graph(self) -> None:
        if self.entrypoint not in self.nodes:
            raise GraphError(f"Entrypoint {self.entrypoint!r} is not a node")
        for e in self.static_edges:
            if e.source not in self.nodes:
                raise GraphError(f"Edge source {e.source!r} is not a node")
            if e.target not in self.nodes and e.target != END:
                raise GraphError(f"Edge target {e.target!r} is not a node or END")
        for ce in self.conditional_edges:
            if ce.source not in self.nodes:
                raise GraphError(f"Conditional source {ce.source!r} is not a node")

    def successors_of(self, name: str) -> list[str]:
        out: list[str] = []
        for e in self.static_edges:
            if e.source == name:
                out.append(e.target)
        return out

    def conditional_for(self, name: str) -> ConditionalEdge | None:
        for ce in self.conditional_edges:
            if ce.source == name:
                return ce
        return None


class GraphBuilder:
    """Fluent API for constructing graphs.

    Example::

        g = (
            GraphBuilder()
            .add_node(greet)
            .add_node(collect)
            .add_edge("greet", "collect")
            .set_entrypoint("greet")
            .compile()
        )
    """

    def __init__(self, name: str = "graph") -> None:
        self.name = name
        self._nodes: dict[str, Node] = {}
        self._static: list[Edge] = []
        self._cond: list[ConditionalEdge] = []
        self._entry: str | None = None

    # --- nodes ---

    def add_node(self, n: Node) -> GraphBuilder:
        if n.name in self._nodes:
            raise GraphError(f"Duplicate node {n.name!r}")
        self._nodes[n.name] = n
        if self._entry is None:
            self._entry = n.name
        return self

    def add_nodes(self, *nodes: Node) -> GraphBuilder:
        for n in nodes:
            self.add_node(n)
        return self

    # --- edges ---

    def add_edge(self, source: str, target: str, *, description: str = "") -> GraphBuilder:
        if source not in self._nodes:
            raise GraphError(f"Cannot add edge from unknown node {source!r}")
        if target not in self._nodes and target != END:
            raise GraphError(f"Cannot add edge to unknown node {target!r}")
        self._static.append(Edge(source=source, target=target, description=description))
        return self

    def add_conditional_edge(
        self,
        source: str,
        route: Callable,
        *,
        description: str = "",
    ) -> GraphBuilder:
        if source not in self._nodes:
            raise GraphError(f"Cannot add conditional edge from unknown node {source!r}")
        self._cond.append(ConditionalEdge(source=source, route=route, description=description))
        return self

    # --- meta ---

    def set_entrypoint(self, name: str) -> GraphBuilder:
        if name not in self._nodes:
            raise GraphError(f"Entrypoint {name!r} is not a node")
        self._entry = name
        return self

    # --- compile ---

    def compile(self) -> Graph:
        if self._entry is None:
            raise GraphError("No entrypoint set")
        graph = Graph(
            entrypoint=self._entry,
            nodes=dict(self._nodes),
            static_edges=list(self._static),
            conditional_edges=list(self._cond),
        )
        graph.validate_graph()
        return graph
