"""Provider-agnostic LLM interface.

The runtime calls `LLM.complete(messages, tools=...)` and gets back a
`ModelResponse`. Provider-specific details (chat templating, tool calling
shapes) live in subclasses; the rest of AgentGraph never sees them.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx
from agentgraph_core.types import JSONValue, Message, ModelResponse, ToolCall


@dataclass(slots=True)
class ToolSpec:
    """Provider-agnostic tool description for the model."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass(slots=True)
class ModelInfo:
    """Catalog entry: which models a provider supports, their prices, etc."""

    name: str
    provider: str
    context_window: int = 8192
    input_cost_per_1k: float = 0.0  # USD
    output_cost_per_1k: float = 0.0
    supports_tools: bool = True
    supports_vision: bool = False


@dataclass(slots=True)
class LLMConfig:
    """Configuration for a single LLM connection."""

    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_s: float = 60.0
    extra: dict[str, JSONValue] = field(default_factory=dict)


class LLM(ABC):
    """Abstract base class for LLM providers."""

    # Subclasses set to a non-empty string. The registry uses this to
    # route `LLM.for_config(config)` to the right provider.
    name: ClassVar[str] = ""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> ModelResponse:
        """Send a chat completion request and return a unified response."""
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Return the catalog of models this provider exposes."""
        ...

    # --- helpers ---

    def _http(self) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return httpx.AsyncClient(
            base_url=self.config.base_url or "",
            timeout=self.config.timeout_s,
            headers=headers,
        )

    def _maybe_parse_tool_calls(self, raw: list[dict[str, Any]] | None) -> list[ToolCall]:
        if not raw:
            return []
        out: list[ToolCall] = []
        for tc in raw:
            args = tc.get("function", {}).get("arguments", {}) if "function" in tc else tc.get("input", {})
            if isinstance(args, str):
                import orjson as _json

                args = _json.loads(args) if args else {}
            out.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("function", {}).get("name", tc.get("name", "")),
                    arguments=args or {},
                )
            )
        return out


# A minimal provider registry. Plugins can call `register_provider` to
# register their own. Built-in providers register on import.
_REGISTRY: dict[str, type[LLM]] = {}


def register_provider(cls: type[LLM]) -> type[LLM]:
    if not cls.name:
        raise ValueError(f"LLM subclass {cls.__name__} must set `name`")
    _REGISTRY[cls.name] = cls
    return cls


def registry() -> dict[str, type[LLM]]:
    return dict(_REGISTRY)


def llm_for_config(config: LLMConfig) -> LLM:
    """Resolve a config to an `LLM` instance using the provider registry."""
    if config.provider not in _REGISTRY:
        raise ValueError(
            f"Unknown LLM provider {config.provider!r}. "
            f"Available: {sorted(_REGISTRY)}. "
            f"Set AG_LLM_PROVIDER and AG_LLM_MODEL, or pass an explicit LLMConfig."
        )
    return _REGISTRY[config.provider](config)


# Default model per provider, used when AG_LLM_MODEL is unset.
_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "ollama": "llama3.3",
}

# Which environment variable holds the API key for each provider.
_PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def default_llm_config(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> LLMConfig:
    """Build the default `LLMConfig` from the environment.

    Resolution order:
      - provider:  argument -> ``AG_LLM_PROVIDER`` -> ``"openai"``
      - model:     argument -> ``AG_LLM_MODEL`` -> provider default
      - api_key:   the provider's key env var (e.g. ``OPENAI_API_KEY``)

    Fails fast with a clear error if the selected provider requires an API
    key and none is configured. This prevents agents from silently running
    against a fake or misconfigured backend in production.
    """
    provider = provider or os.environ.get("AG_LLM_PROVIDER") or "openai"
    if provider not in _REGISTRY:
        raise ValueError(
            f"Unknown LLM provider {provider!r}. Available: {sorted(_REGISTRY)}."
        )
    model = model or os.environ.get("AG_LLM_MODEL") or _DEFAULT_MODELS.get(provider)
    if not model:
        raise ValueError(
            f"No model configured for provider {provider!r}. "
            f"Set AG_LLM_MODEL."
        )
    key_env = _PROVIDER_KEY_ENV.get(provider)
    if key_env and not os.environ.get(key_env):
        raise RuntimeError(
            f"LLM provider {provider!r} requires an API key but {key_env} is not set. "
            f"Export {key_env}, or select a local provider with "
            f"AG_LLM_PROVIDER=ollama."
        )
    return LLMConfig(provider=provider, model=model, temperature=temperature)
