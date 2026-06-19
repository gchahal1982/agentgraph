"""Anthropic provider."""
from __future__ import annotations

import os
from typing import Any, ClassVar

from agentgraph_core.types import Message, ModelResponse, Role, Usage

from agentgraph_llm.base import LLM, LLMConfig, ModelInfo, ToolSpec, register_provider


@register_provider
class AnthropicLLM(LLM):
    name = "anthropic"

    CATALOG: ClassVar[list[ModelInfo]] = [
        ModelInfo("claude-3-7-sonnet-20250219", "anthropic", 200_000, 0.003, 0.015, True, True),
        ModelInfo("claude-3-5-sonnet-20241022", "anthropic", 200_000, 0.003, 0.015, True, True),
        ModelInfo("claude-3-5-haiku-20241022", "anthropic", 200_000, 0.0008, 0.004, True, False),
    ]

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        if not self.config.api_key:
            self.config.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.config.base_url:
            self.config.base_url = "https://api.anthropic.com/v1"

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> ModelResponse:
        system, body = _split_system(messages)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens or 4096,
            "system": system,
            "messages": body,
            "temperature": self.config.temperature,
        }
        if tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]
        async with self._http() as client:
            r = await client.post(
                "/messages",
                json=payload,
                headers={"anthropic-version": "2023-06-01"},
            )
            r.raise_for_status()
            data = r.json()

        text = ""
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    _ToolCallShim(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    )
                )
        u = Usage(
            prompt_tokens=data.get("usage", {}).get("input_tokens", 0),
            completion_tokens=data.get("usage", {}).get("output_tokens", 0),
            total_tokens=(
                data.get("usage", {}).get("input_tokens", 0)
                + data.get("usage", {}).get("output_tokens", 0)
            ),
            model=self.config.model,
        )
        u.cost_usd = _estimate_cost(self.config.model, u.prompt_tokens, u.completion_tokens)
        return ModelResponse(
            message=Message(role=Role.ASSISTANT, content=text),
            text=text,
            tool_calls=self._maybe_parse_tool_calls(
                [
                    {"id": tc.id, "name": tc.name, "input": tc.arguments}
                    for tc in tool_calls
                ]
            ),
            usage=u,
            finish_reason=data.get("stop_reason", "stop"),
            raw=data,
        )

    def list_models(self) -> list[ModelInfo]:
        return list(self.CATALOG)


def _split_system(messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    body: list[dict[str, Any]] = []
    for m in messages:
        if m.role is Role.SYSTEM:
            system_parts.append(m.content)
        elif m.role is Role.TOOL:
            body.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "",
                            "content": m.content,
                        }
                    ],
                }
            )
        elif m.role is Role.ASSISTANT:
            content: list[dict[str, Any]] = []
            if m.content:
                content.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            body.append({"role": "assistant", "content": content or m.content})
        else:
            body.append({"role": m.role.value, "content": m.content})
    return "\n".join(system_parts), body


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    for info in AnthropicLLM.CATALOG:
        if info.name == model:
            return (prompt_tokens / 1000.0) * info.input_cost_per_1k + (
                completion_tokens / 1000.0
            ) * info.output_cost_per_1k
    return 0.0


class _ToolCallShim:
    __slots__ = ("id", "name", "arguments")

    def __init__(self, id: str, name: str, arguments: dict) -> None:
        self.id = id
        self.name = name
        self.arguments = arguments
