"""In-memory registry of agents the server can run.

Production deployments can subclass this to load agents from disk or a
remote config service. The contract is just `get(name) -> RegisteredAgent`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from agentgraph_runtime.graph import Graph


@dataclass(slots=True)
class RegisteredAgent:
    name: str
    description: str
    vertical: str
    graph: Graph
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, RegisteredAgent] = {}
        self._lock = asyncio.Lock()

    async def register(self, agent: RegisteredAgent) -> None:
        async with self._lock:
            if agent.name in self._by_name:
                raise ValueError(f"Agent {agent.name!r} already registered")
            self._by_name[agent.name] = agent

    def register_sync(self, agent: RegisteredAgent) -> None:
        """Register without acquiring the async lock.

        Used during synchronous app startup (before the event loop owns the
        registry). Safe because startup is single-threaded.
        """
        if agent.name in self._by_name:
            raise ValueError(f"Agent {agent.name!r} already registered")
        self._by_name[agent.name] = agent

    async def unregister(self, name: str) -> None:
        async with self._lock:
            self._by_name.pop(name, None)

    async def get(self, name: str) -> RegisteredAgent:
        async with self._lock:
            if name not in self._by_name:
                raise KeyError(f"Agent {name!r} not found")
            return self._by_name[name]

    async def list(self) -> list[RegisteredAgent]:
        async with self._lock:
            return list(self._by_name.values())
