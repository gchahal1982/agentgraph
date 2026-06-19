"""LLM provider abstraction for AgentGraph.

Implementations: OpenAI, Anthropic, Ollama, and a `Mock` provider used in
tests. Vertical packs and the SDK depend only on this module's public API.
"""
from agentgraph_llm.anthropic import AnthropicLLM
from agentgraph_llm.base import (
    LLM,
    LLMConfig,
    ModelInfo,
    ToolSpec,
    register_provider,
    registry,
)
from agentgraph_llm.mock import MockLLM, mock_response
from agentgraph_llm.ollama import OllamaLLM
from agentgraph_llm.openai_compat import OpenAICompatLLM

__all__ = [
    "LLM",
    "LLMConfig",
    "ModelInfo",
    "ToolSpec",
    "registry",
    "register_provider",
    "MockLLM",
    "mock_response",
    "OpenAICompatLLM",
    "AnthropicLLM",
    "OllamaLLM",
]
