"""Core primitives: ids, types, tools, audit, rbac, observability."""
from __future__ import annotations

import pytest
from agentgraph_core.audit import AuditAction, InMemoryAuditLog, make_event
from agentgraph_core.errors import ToolError
from agentgraph_core.ids import new_id, new_run_id, new_thread_id
from agentgraph_core.observability import span
from agentgraph_core.rbac import Permission, Principal, RbacRole
from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue, Message, Role, ToolResult


def test_ids_are_unique() -> None:
    a = new_id()
    b = new_id()
    assert a != b
    assert new_run_id().startswith("run_")
    assert new_thread_id().startswith("thr_")


def test_message_round_trip() -> None:
    m = Message(role=Role.USER, content="hello")
    assert m.role is Role.USER
    assert m.content == "hello"
    # JSON-serializable
    import orjson as _json

    _json.dumps(m.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_tool_decorator_dispatch() -> None:
    @tool(description="Add two numbers")
    async def add(ctx: ToolContext, a: int, b: int) -> dict[str, JSONValue]:
        return {"sum": a + b}

    ctx = ToolContext(run_id="run_x", thread_id="thr_x", principal_id=None, state={})
    result = await add(ctx, a=2, b=3)
    assert isinstance(result, ToolResult)
    import orjson as _json

    body = _json.loads(result.content)
    assert body["sum"] == 5


@pytest.mark.asyncio
async def test_tool_returns_error() -> None:
    @tool(description="A tool that always fails")
    async def boom(ctx: ToolContext) -> str:
        raise ToolError("intentional failure")

    ctx = ToolContext(run_id="r", thread_id="t", principal_id=None, state={})
    result = await boom(ctx)
    assert result.error is not None
    assert "intentional failure" in result.error


def test_audit_log_round_trip() -> None:
    import asyncio

    log = InMemoryAuditLog()

    async def go():
        await log.write(
            make_event(
                run_id="r1",
                thread_id="t1",
                action=AuditAction.RUN_START,
                actor="system",
            )
        )
        await log.write(
            make_event(
                run_id="r1",
                thread_id="t1",
                action=AuditAction.MODEL_CALL,
                actor="node",
            )
        )

    asyncio.run(go())
    out = asyncio.run(log.query(run_id="r1"))
    assert len(out) == 2


def test_principal_permissions() -> None:
    p = Principal(id="u1", roles=[RbacRole.CLINICIAN])
    assert p.has(Permission.READ_PHI)
    assert p.has(Permission.WRITE_DATA)
    assert not p.has(Permission.ADMIN)


def test_observability_span_records_duration() -> None:
    with span("test") as s:
        _ = 1 + 1
    assert s.end is not None
    assert s.duration_ms >= 0
