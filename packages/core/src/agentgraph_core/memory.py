"""Memory primitives.

Two layers: short-term thread memory (the in-flight message list) and
long-term semantic memory (vector store). Vertical packs decide what to
store; the runtime just gives them an interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from agentgraph_core.types import Message


class Memory(ABC):
    """Long-term memory interface.

    Implementations are responsible for embedding, indexing, and ranking.
    The runtime only requires `search` and `add` so it can be swapped
    between vector stores without changing agent code.
    """

    @abstractmethod
    async def add(self, thread_id: str, message: Message) -> None: ...

    @abstractmethod
    async def search(
        self, thread_id: str, query: str, *, limit: int = 5
    ) -> list[Message]: ...

    @abstractmethod
    async def clear(self, thread_id: str) -> None: ...


class InMemoryMemory(Memory):
    """Trivial in-process memory for tests and single-node deployments."""

    def __init__(self) -> None:
        self._by_thread: dict[str, list[Message]] = {}

    async def add(self, thread_id: str, message: Message) -> None:
        self._by_thread.setdefault(thread_id, []).append(message)

    async def search(
        self, thread_id: str, query: str, *, limit: int = 5
    ) -> list[Message]:
        # Substring match; good enough for tests and small dev runs.
        q = query.lower()
        all_msgs = self._by_thread.get(thread_id, [])
        matches = [m for m in all_msgs if q in m.content.lower()]
        return list(matches[-limit:])

    async def clear(self, thread_id: str) -> None:
        self._by_thread.pop(thread_id, None)


class ThreadBuffer:
    """Mutable short-term buffer holding the active conversation.

    Distinct from `Memory` (long-term). One per run; cleared when the run
    completes unless the vertical persists it.
    """

    __slots__ = ("_messages",)

    def __init__(self, initial: Iterable[Message] | None = None) -> None:
        self._messages: list[Message] = list(initial or [])

    def __len__(self) -> int:
        return len(self._messages)

    def __iter__(self):
        return iter(self._messages)

    def append(self, message: Message) -> None:
        self._messages.append(message)

    def extend(self, messages: Iterable[Message]) -> None:
        self._messages.extend(messages)

    def replace(self, messages: list[Message]) -> None:
        self._messages = list(messages)

    def to_list(self) -> list[Message]:
        return list(self._messages)
