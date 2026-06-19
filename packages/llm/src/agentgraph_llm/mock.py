"""Deterministic in-process LLM for tests and offline development.

Vertical packs use this to enable CI without API keys. Users can register
their own canned responses per node name.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

from agentgraph_core.types import Message, ModelResponse, Role, ToolCall, Usage

from agentgraph_llm.base import LLM, LLMConfig, ModelInfo, ToolSpec, register_provider

Handler = Callable[[list[Message], list[ToolSpec] | None], ModelResponse]


@dataclass(slots=True)
class _Scripted:
    """A scripted response queue. Each call pops the next entry, falling
    back to `default` once the queue is exhausted."""

    responses: list[ModelResponse] = field(default_factory=list)
    default: ModelResponse = field(default_factory=ModelResponse)


@register_provider
class MockLLM(LLM):
    """A scripted LLM used in tests.

    Usage::

        llm = MockLLM(LLMConfig(provider="mock", model="mock-1"))
        MockLLM.script("node_a", ModelResponse(text="hi"))
        resp = await llm.complete([Message(role=Role.USER, content="hello")])
    """

    name: ClassVar[str] = "mock"

    # node_name -> handler
    _handlers: ClassVar[dict[str, Handler]] = {}

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._queue: list[ModelResponse] = []
        self._default = ModelResponse(text="")
        self._scripted: dict[str, _Scripted] = {}

    @classmethod
    def script(cls, node_name: str, *responses: ModelResponse) -> None:
        cls._handlers[node_name] = _make_handler(list(responses))

    @classmethod
    def reset(cls) -> None:
        cls._handlers.clear()

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> ModelResponse:
        # Try to find a handler whose name appears in the last user message.
        last = messages[-1].content if messages else ""
        for node, h in self._handlers.items():
            if node in last:
                return h(messages, tools)
        return self._default

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name="mock-1", provider="mock")]


def _make_handler(responses: list[ModelResponse]) -> Handler:
    idx = 0

    def _h(messages: list[Message], tools: list[ToolSpec] | None) -> ModelResponse:
        nonlocal idx
        if idx < len(responses):
            r = responses[idx]
            idx += 1
            return r
        return ModelResponse(text="")

    return _h


def mock_response(
    text: str = "",
    *,
    tool_calls: list[ToolCall] | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> ModelResponse:
    """Helper to build a `ModelResponse` for `MockLLM.script(...)`."""
    return ModelResponse(
        text=text,
        message=Message(role=Role.ASSISTANT, content=text) if text else None,
        tool_calls=tool_calls or [],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model="mock-1",
        ),
        finish_reason="tool_calls" if tool_calls else "stop",
    )
