"""Storage backends for the audit log.

Three implementations ship:

- `InMemoryAuditLog`  - ephemeral, used only by the test suite.
- `SQLiteAuditLog`    - durable, file-backed, zero external dependencies.
                        This is the default for single-node deployments.
- `PostgresAuditLog`  - durable, multi-node, backed by asyncpg.

All three implement the `AuditLog` interface. Select one at runtime with
`audit_log_from_url(url)` (see `agentgraph_core.storage`).
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

import orjson as _json
from pydantic import BaseModel, Field, field_validator

from agentgraph_core.ids import new_id
from agentgraph_core.redaction import redact_sensitive
from agentgraph_core.types import JSONValue


class AuditAction(str, Enum):
    RUN_START = "run.start"
    RUN_END = "run.end"
    MODEL_CALL = "model.call"
    TOOL_CALL = "tool.call"
    POLICY_DECISION = "policy.decision"
    HUMAN_HANDOFF = "human.handoff"
    RETRY = "run.retry"
    ERROR = "run.error"


class AuditEvent(BaseModel):
    """Single audit record."""

    id: str = Field(default_factory=new_id)
    ts: float = Field(default_factory=time.time)
    run_id: str
    thread_id: str
    principal_id: str | None
    action: AuditAction
    actor: str  # node name, tool name, "system", etc.
    payload: dict[str, JSONValue] = Field(default_factory=dict)
    metadata: dict[str, JSONValue] = Field(default_factory=dict)

    @field_validator("payload", "metadata", mode="before")
    @classmethod
    def redact_credentials(cls, value: Any) -> dict[str, JSONValue]:
        redacted = redact_sensitive(value or {})
        if not isinstance(redacted, dict):
            raise ValueError("audit payloads and metadata must be objects")
        return redacted


def _redacted_event(event: AuditEvent) -> AuditEvent:
    """Revalidate a copy so mutations cannot bypass boundary redaction."""
    return AuditEvent.model_validate(event.model_dump(mode="python"))


class AuditLog(ABC):
    """Durable audit log interface."""

    @abstractmethod
    async def write(self, event: AuditEvent) -> None: ...

    @abstractmethod
    async def query(
        self, *, run_id: str | None = None, thread_id: str | None = None, limit: int = 100
    ) -> list[AuditEvent]: ...

    async def close(self) -> None:  # pragma: no cover - optional override
        """Release any underlying resources (connections, files)."""
        return None


class InMemoryAuditLog(AuditLog):
    """Ephemeral audit log used by the test suite.

    Not durable: events are lost on process exit. Production deployments
    use `SQLiteAuditLog` or `PostgresAuditLog`.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def write(self, event: AuditEvent) -> None:
        self._events.append(_redacted_event(event))

    async def query(
        self, *, run_id: str | None = None, thread_id: str | None = None, limit: int = 100
    ) -> list[AuditEvent]:
        out = self._events
        if run_id is not None:
            out = [e for e in out if e.run_id == run_id]
        if thread_id is not None:
            out = [e for e in out if e.thread_id == thread_id]
        return out[-limit:]

    def __len__(self) -> int:
        return len(self._events)


_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id            TEXT PRIMARY KEY,
    ts            REAL NOT NULL,
    run_id        TEXT NOT NULL,
    thread_id     TEXT NOT NULL,
    principal_id  TEXT,
    action        TEXT NOT NULL,
    actor         TEXT NOT NULL,
    payload       TEXT NOT NULL,
    metadata      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_events (run_id, ts);
CREATE INDEX IF NOT EXISTS ix_audit_thread ON audit_events (thread_id, ts);
"""


class SQLiteAuditLog(AuditLog):
    """Durable, file-backed audit log with no external dependencies.

    Writes are serialized through an asyncio lock and executed on a thread
    pool so the event loop is never blocked. This is the default audit log
    for single-node deployments.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_AUDIT_DDL)
        self._conn.commit()

    async def write(self, event: AuditEvent) -> None:
        event = _redacted_event(event)
        async with self._lock:
            await asyncio.to_thread(self._write_sync, event)

    def _write_sync(self, event: AuditEvent) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO audit_events "
            "(id, ts, run_id, thread_id, principal_id, action, actor, payload, metadata) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event.id,
                event.ts,
                event.run_id,
                event.thread_id,
                event.principal_id,
                event.action.value,
                event.actor,
                _json.dumps(event.payload).decode(),
                _json.dumps(event.metadata).decode(),
            ),
        )
        self._conn.commit()

    async def query(
        self, *, run_id: str | None = None, thread_id: str | None = None, limit: int = 100
    ) -> list[AuditEvent]:
        async with self._lock:
            return await asyncio.to_thread(self._query_sync, run_id, thread_id, limit)

    def _query_sync(
        self, run_id: str | None, thread_id: str | None, limit: int
    ) -> list[AuditEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if thread_id is not None:
            clauses.append("thread_id = ?")
            params.append(thread_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT id, ts, run_id, thread_id, principal_id, action, actor, payload, metadata "
            f"FROM audit_events{where} ORDER BY ts DESC LIMIT ?",
            params,
        ).fetchall()
        rows.reverse()
        return [_row_to_event(r) for r in rows]

    async def close(self) -> None:
        async with self._lock:
            self._conn.close()


class PostgresAuditLog(AuditLog):
    """Durable, multi-node audit log backed by Postgres (asyncpg).

    Requires the `postgres` extra: ``pip install 'agentgraph-core[postgres]'``.
    Call `await store.setup()` once at startup to create the schema, or rely
    on the lazy schema creation performed on first write.
    """

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: Any = None
        self._lock = asyncio.Lock()

    async def _ensure_pool(self) -> Any:
        if self._pool is None:
            async with self._lock:
                if self._pool is None:
                    try:
                        import asyncpg
                    except ImportError as e:  # pragma: no cover
                        raise RuntimeError(
                            "PostgresAuditLog requires asyncpg. "
                            "Install with: pip install 'agentgraph-core[postgres]'"
                        ) from e
                    self._pool = await asyncpg.create_pool(
                        self._dsn, min_size=self._min_size, max_size=self._max_size
                    )
                    await self._setup(self._pool)
        return self._pool

    async def _setup(self, pool: Any) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id            TEXT PRIMARY KEY,
                    ts            DOUBLE PRECISION NOT NULL,
                    run_id        TEXT NOT NULL,
                    thread_id     TEXT NOT NULL,
                    principal_id  TEXT,
                    action        TEXT NOT NULL,
                    actor         TEXT NOT NULL,
                    payload       JSONB NOT NULL,
                    metadata      JSONB NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_events (run_id, ts);
                CREATE INDEX IF NOT EXISTS ix_audit_thread ON audit_events (thread_id, ts);
                """
            )

    async def write(self, event: AuditEvent) -> None:
        event = _redacted_event(event)
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO audit_events "
                "(id, ts, run_id, thread_id, principal_id, action, actor, payload, metadata) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING",
                event.id,
                event.ts,
                event.run_id,
                event.thread_id,
                event.principal_id,
                event.action.value,
                event.actor,
                _json.dumps(event.payload).decode(),
                _json.dumps(event.metadata).decode(),
            )

    async def query(
        self, *, run_id: str | None = None, thread_id: str | None = None, limit: int = 100
    ) -> list[AuditEvent]:
        pool = await self._ensure_pool()
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            params.append(run_id)
            clauses.append(f"run_id = ${len(params)}")
        if thread_id is not None:
            params.append(thread_id)
            clauses.append(f"thread_id = ${len(params)}")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, ts, run_id, thread_id, principal_id, action, actor, payload, metadata "
                f"FROM audit_events{where} ORDER BY ts DESC LIMIT ${len(params)}",
                *params,
            )
        rows = list(reversed(rows))
        return [
            AuditEvent(
                id=r["id"],
                ts=r["ts"],
                run_id=r["run_id"],
                thread_id=r["thread_id"],
                principal_id=r["principal_id"],
                action=AuditAction(r["action"]),
                actor=r["actor"],
                payload=_json.loads(r["payload"]) if isinstance(r["payload"], str | bytes) else r["payload"],
                metadata=_json.loads(r["metadata"]) if isinstance(r["metadata"], str | bytes) else r["metadata"],
            )
            for r in rows
        ]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def _row_to_event(r: tuple[Any, ...]) -> AuditEvent:
    return AuditEvent(
        id=r[0],
        ts=r[1],
        run_id=r[2],
        thread_id=r[3],
        principal_id=r[4],
        action=AuditAction(r[5]),
        actor=r[6],
        payload=_json.loads(r[7]) if r[7] else {},
        metadata=_json.loads(r[8]) if r[8] else {},
    )


def make_event(
    *,
    run_id: str,
    thread_id: str,
    action: AuditAction,
    actor: str,
    principal_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        run_id=run_id,
        thread_id=thread_id,
        principal_id=principal_id,
        action=action,
        actor=actor,
        payload=payload or {},
        metadata=metadata or {},
    )
