"""Durable checkpoint store.

The runtime snapshots `GraphState` after every node so runs can be
resumed across process restarts. The default store is in-process; the
Postgres-backed store is suitable for production multi-tenant deployments.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from agentgraph_core.ids import new_id
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


class InMemoryCheckpointStore(CheckpointStore):
    """In-process checkpoint store.

    Suitable for tests, local development, and single-shot runs. State is
    lost on process exit; production deployments should use the
    Postgres-backed store.
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
