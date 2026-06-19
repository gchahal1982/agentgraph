"""Durable checkpoint store.

The runtime snapshots `GraphState` after every node so runs can be resumed
across process restarts. Three backends ship:

- `InMemoryCheckpointStore` - ephemeral, used by the test suite.
- `SQLiteCheckpointStore`    - durable, file-backed, no external deps. Default.
- `PostgresCheckpointStore`  - durable, multi-node, backed by asyncpg.

Select one with `checkpoint_store_from_url(url)`.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import orjson as _json
from agentgraph_core.ids import new_id
from agentgraph_core.storage import _sqlite_path, default_storage_url
from pydantic import BaseModel, Field


class Checkpoint(BaseModel):
    """A single persisted snapshot of a run."""

    id: str = Field(default_factory=new_id)
    run_id: str
    thread_id: str
    node: str
    state: dict[str, Any]
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CheckpointStore(ABC):
    """Durable state for graph runs."""

    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> None: ...

    @abstractmethod
    async def load_latest(self, run_id: str) -> Checkpoint | None: ...

    @abstractmethod
    async def list_for_thread(self, thread_id: str) -> list[Checkpoint]: ...

    async def close(self) -> None:  # pragma: no cover - optional override
        return None


class InMemoryCheckpointStore(CheckpointStore):
    """Ephemeral checkpoint store used by the test suite.

    Not durable: state is lost on process exit. Production deployments use
    `SQLiteCheckpointStore` or `PostgresCheckpointStore`.
    """

    def __init__(self) -> None:
        self._by_run: dict[str, list[Checkpoint]] = {}
        self._by_thread: dict[str, list[Checkpoint]] = {}

    async def save(self, checkpoint: Checkpoint) -> None:
        self._by_run.setdefault(checkpoint.run_id, []).append(checkpoint)
        self._by_thread.setdefault(checkpoint.thread_id, []).append(checkpoint)

    async def load_latest(self, run_id: str) -> Checkpoint | None:
        cps = self._by_run.get(run_id, [])
        return cps[-1] if cps else None

    async def list_for_thread(self, thread_id: str) -> list[Checkpoint]:
        return list(self._by_thread.get(thread_id, []))


_CKPT_DDL = """
CREATE TABLE IF NOT EXISTS checkpoints (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    thread_id   TEXT NOT NULL,
    node        TEXT NOT NULL,
    state       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    metadata    TEXT NOT NULL,
    seq         INTEGER
);
CREATE INDEX IF NOT EXISTS ix_ckpt_run ON checkpoints (run_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ckpt_thread ON checkpoints (thread_id, created_at);
"""


class SQLiteCheckpointStore(CheckpointStore):
    """Durable, file-backed checkpoint store with no external dependencies.

    This is the default for single-node deployments. Writes are serialized
    through an asyncio lock and run on a thread pool to keep the event loop
    responsive.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._seq = 0
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_CKPT_DDL)
        self._conn.commit()
        row = self._conn.execute("SELECT COALESCE(MAX(seq), 0) FROM checkpoints").fetchone()
        self._seq = int(row[0] or 0)

    async def save(self, checkpoint: Checkpoint) -> None:
        async with self._lock:
            self._seq += 1
            await asyncio.to_thread(self._save_sync, checkpoint, self._seq)

    def _save_sync(self, c: Checkpoint, seq: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO checkpoints "
            "(id, run_id, thread_id, node, state, created_at, metadata, seq) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                c.id,
                c.run_id,
                c.thread_id,
                c.node,
                _json.dumps(c.state).decode(),
                c.created_at,
                _json.dumps(c.metadata).decode(),
                seq,
            ),
        )
        self._conn.commit()

    async def load_latest(self, run_id: str) -> Checkpoint | None:
        async with self._lock:
            return await asyncio.to_thread(self._load_latest_sync, run_id)

    def _load_latest_sync(self, run_id: str) -> Checkpoint | None:
        row = self._conn.execute(
            "SELECT id, run_id, thread_id, node, state, created_at, metadata "
            "FROM checkpoints WHERE run_id = ? ORDER BY seq DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return _row_to_ckpt(row) if row else None

    async def list_for_thread(self, thread_id: str) -> list[Checkpoint]:
        async with self._lock:
            return await asyncio.to_thread(self._list_for_thread_sync, thread_id)

    def _list_for_thread_sync(self, thread_id: str) -> list[Checkpoint]:
        rows = self._conn.execute(
            "SELECT id, run_id, thread_id, node, state, created_at, metadata "
            "FROM checkpoints WHERE thread_id = ? ORDER BY seq ASC",
            (thread_id,),
        ).fetchall()
        return [_row_to_ckpt(r) for r in rows]

    async def close(self) -> None:
        async with self._lock:
            self._conn.close()


class PostgresCheckpointStore(CheckpointStore):
    """Durable, multi-node checkpoint store backed by Postgres (asyncpg).

    Requires the `postgres` extra: ``pip install 'agentgraph-runtime[postgres]'``.
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
                            "PostgresCheckpointStore requires asyncpg. "
                            "Install with: pip install 'agentgraph-runtime[postgres]'"
                        ) from e
                    self._pool = await asyncpg.create_pool(
                        self._dsn, min_size=self._min_size, max_size=self._max_size
                    )
                    async with self._pool.acquire() as conn:
                        await conn.execute(
                            """
                            CREATE TABLE IF NOT EXISTS checkpoints (
                                id          TEXT PRIMARY KEY,
                                run_id      TEXT NOT NULL,
                                thread_id   TEXT NOT NULL,
                                node        TEXT NOT NULL,
                                state       JSONB NOT NULL,
                                created_at  DOUBLE PRECISION NOT NULL,
                                metadata    JSONB NOT NULL,
                                seq         BIGSERIAL
                            );
                            CREATE INDEX IF NOT EXISTS ix_ckpt_run ON checkpoints (run_id, seq);
                            CREATE INDEX IF NOT EXISTS ix_ckpt_thread ON checkpoints (thread_id, seq);
                            """
                        )
        return self._pool

    async def save(self, checkpoint: Checkpoint) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO checkpoints (id, run_id, thread_id, node, state, created_at, metadata) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO NOTHING",
                checkpoint.id,
                checkpoint.run_id,
                checkpoint.thread_id,
                checkpoint.node,
                _json.dumps(checkpoint.state).decode(),
                checkpoint.created_at,
                _json.dumps(checkpoint.metadata).decode(),
            )

    async def load_latest(self, run_id: str) -> Checkpoint | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, run_id, thread_id, node, state, created_at, metadata "
                "FROM checkpoints WHERE run_id = $1 ORDER BY seq DESC LIMIT 1",
                run_id,
            )
        return _pg_row_to_ckpt(row) if row else None

    async def list_for_thread(self, thread_id: str) -> list[Checkpoint]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, run_id, thread_id, node, state, created_at, metadata "
                "FROM checkpoints WHERE thread_id = $1 ORDER BY seq ASC",
                thread_id,
            )
        return [_pg_row_to_ckpt(r) for r in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def _row_to_ckpt(r: tuple[Any, ...]) -> Checkpoint:
    return Checkpoint(
        id=r[0],
        run_id=r[1],
        thread_id=r[2],
        node=r[3],
        state=_json.loads(r[4]),
        created_at=r[5],
        metadata=_json.loads(r[6]) if r[6] else {},
    )


def _pg_row_to_ckpt(r: Any) -> Checkpoint:
    def _load(v: Any) -> Any:
        return _json.loads(v) if isinstance(v, str | bytes) else v

    return Checkpoint(
        id=r["id"],
        run_id=r["run_id"],
        thread_id=r["thread_id"],
        node=r["node"],
        state=_load(r["state"]),
        created_at=r["created_at"],
        metadata=_load(r["metadata"]) if r["metadata"] else {},
    )


def checkpoint_store_from_url(url: str | None = None) -> CheckpointStore:
    """Construct a `CheckpointStore` from a storage URL."""
    url = url or default_storage_url()
    scheme = urlparse(url).scheme
    if url.startswith("memory://") or scheme == "memory":
        return InMemoryCheckpointStore()
    if scheme.startswith("sqlite"):
        return SQLiteCheckpointStore(_sqlite_path(url))
    if scheme.startswith("postgres"):
        return PostgresCheckpointStore(url)
    raise ValueError(f"Unsupported storage URL scheme: {url!r}")
