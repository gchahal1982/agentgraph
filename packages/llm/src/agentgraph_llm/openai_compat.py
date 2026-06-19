"""OpenAI-compatible chat provider.

Works against OpenAI, Azure OpenAI (with `base_url` and `api_key` set), and
any local server that speaks the OpenAI chat completions format (vLLM,
LM Studio, llama.cpp's server, etc.).
"""
from __future__ import annotations

import os
from typing import Any, ClassVar

import orjson as _json
from agentgraph_core.types import Message, ModelResponse, Role, Usage

from agentgraph_llm.base import LLM, LLMConfig, ModelInfo, ToolSpec, register_provider


@register_provider
class OpenAICompatLLM(LLM):
    name = "openai"

    CATALOG: ClassVar[list[ModelInfo]] = [
        ModelInfo("gpt-4o", "openai", 128_000, 0.0025, 0.01, True, True),
        ModelInfo("gpt-4o-mini", "openai", 128_000, 0.00015, 0.0006, True, True),
        ModelInfo("gpt-4.1", "openai", 1_000_000, 0.002, 0.008, True, True),
        ModelInfo("gpt-4.1-mini", "openai", 1_000_000, 0.0004, 0.0016, True, True),
        ModelInfo("o4-mini", "openai", 200_000, 0.0011, 0.0044, True, False),
    ]

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        if not self.config.api_key:
            self.config.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.config.base_url:
            self.config.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [_message_to_openai(m) for m in messages],
            "temperature": self.config.temperature,
        }
        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens
        if tools:
            payload["tools"] = [_tool_to_openai(t) for t in tools]
            payload["tool_choice"] = tool_choice or "auto"

        async with self._http() as client:
            r = await client.post("/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()

        choice = data["choices"][0]
        msg = choice.get("message", {})
        text = msg.get("content") or ""
        tool_calls = self._maybe_parse_tool_calls(msg.get("tool_calls"))
        usage = data.get("usage", {})
        u = Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model=self.config.model,
        )
        u.cost_usd = _estimate_cost(self.config.model, u.prompt_tokens, u.completion_tokens)
        return ModelResponse(
            message=Message(role=Role.ASSISTANT, content=text, tool_calls=tool_calls),
            text=text,
            tool_calls=tool_calls,
            usage=u,
            finish_reason=choice.get("finish_reason", "stop"),
            raw=data,
        )

    def list_models(self) -> list[ModelInfo]:
        return list(self.CATALOG)


def _message_to_openai(m: Message) -> dict[str, Any]:
    out: dict[str, Any] = {"role": m.role.value, "content": m.content}
    if m.name:
        out["name"] = m.name
    if m.tool_call_id:
        out["tool_call_id"] = m.tool_call_id
    if m.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": _json.dumps(tc.arguments).decode("utf-8"),
                },
            }
            for tc in m.tool_calls
        ]
    return out


def _tool_to_openai(t: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        },
    }


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    for info in OpenAICompatLLM.CATALOG:
        if info.name == model:
            return (prompt_tokens / 1000.0) * info.input_cost_per_1k + (
                completion_tokens / 1000.0
            ) * info.output_cost_per_1k
    return 0.0
