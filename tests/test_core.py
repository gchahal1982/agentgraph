"""Core primitives: ids, types, tools, audit, rbac, observability."""
from __future__ import annotations

import pytest
import structlog
from agentgraph_core.audit import AuditAction, AuditEvent, InMemoryAuditLog, make_event
from agentgraph_core.errors import ToolError
from agentgraph_core.ids import new_id, new_run_id, new_thread_id
from agentgraph_core.observability import StructLogTracer, span
from agentgraph_core.rbac import Permission, Principal, RbacRole
from agentgraph_core.redaction import redact_sensitive
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


def test_redact_sensitive_nested_credentials() -> None:
    secrets = {
        "secret-value",
        "generic-token",
        "private-key-value",
        "token-value",
        "hunter2",
        "key-material",
        "YmFzaWMtdXNlcjpiYXNpYy1wYXNz",
        "db-user:db-password",
        "session-value",
        "VALUE WITH SPACE",
    }
    value = redact_sensitive(
        {
            "api_key": "secret-value",
            "token": "generic-token",
            "private_key": "private-key-value",
            "nested": [
                {"authorization": "Bearer token-value"},
                "password=hunter2; safe text",
                "-----BEGIN PRIVATE KEY-----\nkey-material\n-----END PRIVATE KEY-----",
                "Authorization: Basic YmFzaWMtdXNlcjpiYXNpYy1wYXNz",
                "postgresql://db-user:db-password@db.internal/app",
                "Cookie: session_id=session-value; safe=value",
                'client_secret="VALUE WITH SPACE" safe text',
            ],
        }
    )
    rendered = str(value)
    assert all(secret not in rendered for secret in secrets)
    assert "safe text" in rendered
    assert "safe=value" not in rendered  # Cookie values are conservatively redacted together.


def test_audit_event_redacts_public_payload_and_metadata() -> None:
    event = AuditEvent(
        run_id="run",
        thread_id="thread",
        principal_id=None,
        action=AuditAction.RUN_START,
        actor="test",
        payload={"message": "Authorization: Basic public-api-secret"},
        metadata={"session_id": "metadata-secret", "safe": "context"},
    )
    rendered = event.model_dump_json()
    assert "public-api-secret" not in rendered
    assert "metadata-secret" not in rendered
    assert "context" in rendered


def test_redact_sensitive_preserves_noncredential_metrics() -> None:
    value = redact_sensitive(
        {
            "total_tokens": 42,
            "prompt_tokens": 30,
            "completion_tokens": 12,
            "secretary": "available",
            "cookie_preferences": "essential",
            "access_token": "credential",
            "openai_api_key": "provider-credential",
            "X-API-Key": "header-credential",
        }
    )
    assert value == {
        "total_tokens": 42,
        "prompt_tokens": 30,
        "completion_tokens": 12,
        "secretary": "available",
        "cookie_preferences": "essential",
        "access_token": "[REDACTED]",
        "openai_api_key": "[REDACTED]",
        "X-API-Key": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_audit_write_redacts_post_construction_mutation(tmp_path) -> None:
    from agentgraph_core.audit import SQLiteAuditLog

    event = AuditEvent(
        run_id="run",
        thread_id="thread",
        principal_id=None,
        action=AuditAction.RUN_START,
        actor="test",
    )
    event.payload["token"] = "mutated-secret"
    event.metadata["authorization"] = "Bearer metadata-secret"
    log = SQLiteAuditLog(tmp_path / "audit.db")
    await log.write(event)
    stored = (await log.query(run_id="run"))[0]
    await log.close()
    rendered = stored.model_dump_json()
    assert "mutated-secret" not in rendered
    assert "metadata-secret" not in rendered


def test_structlog_tracer_redacts_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: dict[str, object] = {}

    class FakeLogger:
        def error(self, event: str, **payload: object) -> None:
            emitted.update(event=event, **payload)

        def info(self, event: str, **payload: object) -> None:
            emitted.update(event=event, **payload)

    monkeypatch.setattr(structlog, "get_logger", lambda _name: FakeLogger())
    tracer = StructLogTracer()
    with span("unused") as finished:
        pass
    finished.attributes = {
        "authorization": "Bearer log-secret",
        "safe": "context",
    }
    finished.fail("RuntimeError")
    tracer.on_span_end(finished)
    rendered = str(emitted)
    assert "log-secret" not in rendered
    assert "context" in rendered
    assert "RuntimeError" in rendered


def test_observability_span_records_duration() -> None:
    with span("test") as s:
        _ = 1 + 1
    assert s.end is not None
    assert s.duration_ms >= 0
