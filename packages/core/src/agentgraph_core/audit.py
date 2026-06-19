"""Audit logging.

Every privileged action (tool call, model call with cost, policy decision,
human handoff) emits an `AuditEvent`. The runtime writes these to the
configured `AuditLog`; vertical packs in regulated industries (insurance,
healthcare, compliance) plug in durable storage.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentgraph_core.ids import new_id
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


class AuditLog(ABC):
    """Durable audit log interface."""

    @abstractmethod
    async def write(self, event: AuditEvent) -> None: ...

    @abstractmethod
    async def query(
        self, *, run_id: str | None = None, thread_id: str | None = None, limit: int = 100
    ) -> list[AuditEvent]: ...


class InMemoryAuditLog(AuditLog):
    """Test/dev audit log. Lost on process exit."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def write(self, event: AuditEvent) -> None:
        self._events.append(event)

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
