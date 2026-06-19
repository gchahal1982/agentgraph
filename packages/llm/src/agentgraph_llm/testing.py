"""Test-only LLM provider.

This module is **not** imported by the shipped package. It exists so the
test suite (and local experimentation) can exercise agent execution without
calling a real model or needing an API key.

Register it explicitly in a test fixture::

    from agentgraph_llm.testing import register_test_provider, script
    register_test_provider()
    script("my_node", text="hello")

It is intentionally kept out of `agentgraph_llm.__init__` so production code
cannot accidentally depend on it.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from agentgraph_core.types import Message, ModelResponse, Role, ToolCall, Usage

from agentgraph_llm.base import LLM, LLMConfig, ModelInfo, ToolSpec, register_provider

Handler = Callable[[list[Message], list[ToolSpec] | None], ModelResponse]

TEST_PROVIDER = "test"


class ScriptedLLM(LLM):
    """A scripted LLM for the test suite.

    Responses are registered per node name with `script(...)`. When the last
    user message (or the system prompt) contains a registered node name, the
    corresponding scripted responses are returned in order.

    Named `ScriptedLLM` (not `TestLLM`) so pytest does not attempt to collect
    it as a test class.
    """

    name: ClassVar[str] = TEST_PROVIDER
    _handlers: ClassVar[dict[str, Handler]] = {}

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._default = ModelResponse(text="")

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
        last = messages[-1].content if messages else ""
        for node, handler in self._handlers.items():
            if node in last:
                return handler(messages, tools)
        system = messages[0].content if messages else ""
        for node, handler in self._handlers.items():
            if node in system:
                return handler(messages, tools)
        return self._default

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name="test-model", provider=TEST_PROVIDER)]


# Backwards-compatible alias for fixtures that prefer the shorter name.
TestLLM = ScriptedLLM


def register_test_provider() -> None:
    """Register the scripted provider in the global registry (idempotent)."""
    register_provider(ScriptedLLM)


def script(node_name: str, *responses: ModelResponse) -> None:
    ScriptedLLM.script(node_name, *responses)


def reset() -> None:
    ScriptedLLM.reset()


def _make_handler(responses: list[ModelResponse]) -> Handler:
    idx = 0

    def _handler(messages: list[Message], tools: list[ToolSpec] | None) -> ModelResponse:
        nonlocal idx
        if idx < len(responses):
            r = responses[idx]
            idx += 1
            return r
        return ModelResponse(text="")

    return _handler


def response(
    text: str = "",
    *,
    tool_calls: list[ToolCall] | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> ModelResponse:
    """Build a `ModelResponse` for use with `script(...)`."""
    return ModelResponse(
        text=text,
        message=Message(role=Role.ASSISTANT, content=text) if text else None,
        tool_calls=tool_calls or [],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model="test-model",
        ),
        finish_reason="tool_calls" if tool_calls else "stop",
    )
