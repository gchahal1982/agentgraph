"""Human handoff: pause a run and route it to a human reviewer.

Vertical packs in support, insurance, and healthcare use this to escalate
conversations to licensed agents. The runtime pauses the run, persists
a `Handoff` event, and (optionally) waits for a human reply on the
configured channel.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from agentgraph_core.ids import new_id
from agentgraph_core.types import JSONValue


@dataclass(slots=True)
class Handoff:
    """A request to route a run to a human."""

    run_id: str
    thread_id: str
    reason: str
    id: str = field(default_factory=new_id)
    payload: dict[str, JSONValue] = field(default_factory=dict)
    channel: str = "default"
    priority: int = 0
    resolved: bool = False
    response: str | None = None


class HandoffChannel(ABC):
    """Pluggable destination for handoffs: queue, email, SMS, Slack, etc."""

    @abstractmethod
    async def send(self, handoff: Handoff) -> None: ...

    @abstractmethod
    async def wait_for_response(self, handoff: Handoff, timeout_s: float) -> str | None: ...


class HandoffRouter:
    """Routes `Handoff`s to a channel by name."""

    def __init__(self) -> None:
        self._channels: dict[str, HandoffChannel] = {}

    def register(self, name: str, channel: HandoffChannel) -> None:
        self._channels[name] = channel

    async def route(self, handoff: Handoff) -> None:
        ch = self._channels.get(handoff.channel or "default")
        if ch is None:
            raise KeyError(f"Unknown handoff channel {handoff.channel!r}")
        await ch.send(handoff)

    def get(self, name: str) -> HandoffChannel:
        if name not in self._channels:
            raise KeyError(f"Unknown handoff channel {name!r}")
        return self._channels[name]
