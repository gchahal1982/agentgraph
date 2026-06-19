"""Runtime: graph execution, nodes, edges, checkpoints."""
from __future__ import annotations

import pytest
from agentgraph_core.audit import AuditAction, InMemoryAuditLog
from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_runtime.checkpoint import InMemoryCheckpointStore
from agentgraph_runtime.graph import GraphBuilder
from agentgraph_runtime.node import END, NodeResult, node
from agentgraph_runtime.runtime import Runtime, RuntimeConfig
from agentgraph_runtime.state import GraphState


@node("greet")
async def greet(state: GraphState) -> NodeResult:
    state.values["greeted"] = True
    return NodeResult(next="ask")


@node("ask")
async def ask(state: GraphState) -> NodeResult:
    state.values["asked"] = True
    return NodeResult(next=END)


def _two_node_graph() -> tuple:
    g = (
        GraphBuilder()
        .add_node(greet)
        .add_node(ask)
        .add_edge("greet", "ask")
        .add_edge("ask", END)
        .set_entrypoint("greet")
        .compile()
    )
    return g


@pytest.mark.asyncio
async def test_simple_graph_runs_to_end() -> None:
    g = _two_node_graph()
    rt = Runtime()
    state = await rt.run(g, input={"name": "Ada"})
    assert state.finished
    assert state.values.get("greeted") is True
    assert state.values.get("asked") is True


@pytest.mark.asyncio
async def test_audit_events_written() -> None:
    audit = InMemoryAuditLog()
    g = _two_node_graph()
    rt = Runtime(RuntimeConfig(audit_log=audit))
    await rt.run(g, input={})
    events = await audit.query()
    actions = [e.action for e in events]
    assert AuditAction.RUN_START in actions
    assert AuditAction.RUN_END in actions
    # One model_call-like span per node, but our plain @node doesn't audit
    # model calls. The two events above are what we need to verify.


@pytest.mark.asyncio
async def test_checkpoint_store_saves_state() -> None:
    store = InMemoryCheckpointStore()
    g = _two_node_graph()
    rt = Runtime(RuntimeConfig(checkpoint_store=store))
    state = await rt.run(g, input={})
    cps = await store.list_for_thread(state.run.thread_id)
    # We checkpoint after each node, so at least 2.
    assert len(cps) >= 2
    last = cps[-1]
    assert last.node in ("ask", END)


@pytest.mark.asyncio
async def test_conditional_edge_routes() -> None:
    @node("decide")
    async def decide(state: GraphState) -> NodeResult:
        return NodeResult(next=None)

    async def route(state: GraphState) -> str:
        return "a" if state.run.input.get("path") == "a" else "b"

    @node("a")
    async def a(state: GraphState) -> NodeResult:
        state.values["took_a"] = True
        return NodeResult(end=True)

    @node("b")
    async def b(state: GraphState) -> NodeResult:
        state.values["took_b"] = True
        return NodeResult(end=True)

    g = (
        GraphBuilder()
        .add_node(decide)
        .add_node(a)
        .add_node(b)
        .add_conditional_edge("decide", route)
        .set_entrypoint("decide")
        .compile()
    )
    rt = Runtime()
    s = await rt.run(g, input={"path": "a"})
    assert s.values.get("took_a") is True
    assert "took_b" not in s.values


@pytest.mark.asyncio
async def test_policy_enforcement() -> None:
    @node("phi_node", requires="data.read.phi")
    async def phi_node(state: GraphState) -> NodeResult:
        state.values["phi_seen"] = True
        return NodeResult(end=True)

    g = (
        GraphBuilder()
        .add_node(phi_node)
        .set_entrypoint("phi_node")
        .compile()
    )

    # Without a clinician principal -> PolicyError
    rt = Runtime(RuntimeConfig(principal=Principal(id="u1", roles=[RbacRole.USER])))
    with pytest.raises(Exception):  # noqa: B017 - testing policy rejection
        await rt.run(g, input={})

    # With a clinician principal -> success
    rt = Runtime(RuntimeConfig(principal=Principal(id="doc", roles=[RbacRole.CLINICIAN])))
    state = await rt.run(g, input={})
    assert state.values.get("phi_seen") is True


@pytest.mark.asyncio
async def test_swallow_error_routes_to_on_error() -> None:
    @node("flaky", swallow_errors=True, on_error="recover")
    async def flaky(state: GraphState) -> NodeResult:
        raise RuntimeError("boom")

    @node("recover")
    async def recover(state: GraphState) -> NodeResult:
        state.values["recovered"] = True
        return NodeResult(end=True)

    g = (
        GraphBuilder()
        .add_node(flaky)
        .add_node(recover)
        .add_edge("flaky", "recover")
        .set_entrypoint("flaky")
        .compile()
    )
    rt = Runtime()
    state = await rt.run(g, input={})
    assert state.values.get("recovered") is True
    assert state.error is not None
