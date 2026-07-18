"""LLM provider abstraction for AgentGraph.

Providers ship for OpenAI (and OpenAI-compatible servers), Anthropic, and
Ollama. A configuration resolves to a provider via the registry.

For tests, a scripted provider lives in `agentgraph_llm.testing`; it is not
registered by default so production code cannot accidentally depend on it.
"""
from agentgraph_llm.anthropic import AnthropicLLM
from agentgraph_llm.base import (
    LLM,
    LLMConfig,
    ModelInfo,
    ToolSpec,
    default_llm_config,
    llm_for_config,
    register_provider,
    registry,
)
from agentgraph_llm.ollama import OllamaLLM
from agentgraph_llm.openai_compat import OpenAICompatLLM

__all__ = [
    "LLM",
    "AnthropicLLM",
    "LLMConfig",
    "ModelInfo",
    "OllamaLLM",
    "OpenAICompatLLM",
    "ToolSpec",
    "default_llm_config",
    "llm_for_config",
    "register_provider",
    "registry",
]
