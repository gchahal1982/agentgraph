"""Run and graph state.

A `RunState` is a single execution: the messages, scratch values, and
metadata for one invocation of a graph. A `GraphState` is the graph-level
state container that gets checkpointed between node executions.
"""
from __future__ import annotations

import time
from typing import Any

from agentgraph_core.ids import new_run_id, new_thread_id
from agentgraph_core.types import JSONValue, Message
from pydantic import BaseModel, Field


class RunState(BaseModel):
    """The mutable state of a single run."""

    run_id: str = Field(default_factory=new_run_id)
    thread_id: str = Field(default_factory=new_thread_id)
    principal_id: str | None = None
    started_at: float = Field(default_factory=time.time)
    input: dict[str, JSONValue] = Field(default_factory=dict)
    metadata: dict[str, JSONValue] = Field(default_factory=dict)


class GraphState(BaseModel):
    """Snapshot of all values that nodes have produced so far.

    Nodes read and write to `values`. The runtime takes a copy of this
    object on every checkpoint, so `values` must be JSON-serializable.
    """

    run: RunState = Field(default_factory=RunState)
    values: dict[str, JSONValue] = Field(default_factory=dict)
    messages: list[Message] = Field(default_factory=list)
    current_node: str | None = None
    next_node: str | None = None
    error: str | None = None
    finished: bool = False

    def set(self, key: str, value: JSONValue) -> None:
        self.values[key] = value

    def get(self, key: str, default: JSONValue = None) -> JSONValue:
        return self.values.get(key, default)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def to_checkpoint_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_checkpoint_dict(cls, data: dict[str, Any]) -> GraphState:
        return cls.model_validate(data)
