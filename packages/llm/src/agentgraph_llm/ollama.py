"""Ollama provider (local models via Ollama's OpenAI-compatible endpoint)."""
from __future__ import annotations

import os

from agentgraph_core.types import Message, ModelResponse

from agentgraph_llm.base import LLM, LLMConfig, ModelInfo, ToolSpec, register_provider
from agentgraph_llm.openai_compat import OpenAICompatLLM


@register_provider
class OllamaLLM(LLM):
    name = "ollama"

    DEFAULT_BASE = "http://localhost:11434/v1"

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        if not self.config.base_url:
            self.config.base_url = os.environ.get("OLLAMA_BASE_URL", self.DEFAULT_BASE)
        # Ollama accepts any string in the api_key header; the real auth is
        # the host firewall. We synthesize one so the OpenAI-compat client
        # is happy.
        if not self.config.api_key:
            self.config.api_key = "ollama"
        self._inner = OpenAICompatLLM(self.config)

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> ModelResponse:
        return await self._inner.complete(messages, tools=tools, tool_choice=tool_choice)

    def list_models(self) -> list[ModelInfo]:
        # Ollama is dynamic; users register the specific tags they pull.
        # The catalog here is a sensible default set.
        return [
            ModelInfo("llama3.3", "ollama", 128_000, 0.0, 0.0, True, False),
            ModelInfo("qwen2.5", "ollama", 32_000, 0.0, 0.0, True, False),
            ModelInfo("mistral", "ollama", 32_000, 0.0, 0.0, True, False),
            ModelInfo("deepseek-r1", "ollama", 64_000, 0.0, 0.0, False, False),
        ]
