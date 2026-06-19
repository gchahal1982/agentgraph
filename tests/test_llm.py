"""LLM provider abstraction: registry, mock, dispatch."""
from __future__ import annotations

import pytest
from agentgraph_core.types import Message, Role
from agentgraph_llm.base import LLMConfig, registry
from agentgraph_llm.mock import MockLLM, mock_response


def test_registry_includes_builtins() -> None:
    r = registry()
    assert "mock" in r
    assert "openai" in r
    assert "anthropic" in r
    assert "ollama" in r


@pytest.mark.asyncio
async def test_mock_llm_returns_default() -> None:
    llm = MockLLM(LLMConfig(provider="mock", model="mock-1"))
    MockLLM.reset()
    resp = await llm.complete([Message(role=Role.USER, content="hello")])
    assert resp.text == ""
    MockLLM.reset()


@pytest.mark.asyncio
async def test_mock_llm_scripted() -> None:
    llm = MockLLM(LLMConfig(provider="mock", model="mock-1"))
    MockLLM.reset()
    MockLLM.script("greet", mock_response(text="hi there", prompt_tokens=10, completion_tokens=3))
    resp = await llm.complete([Message(role=Role.USER, content="please greet")])
    assert resp.text == "hi there"
    assert resp.usage.completion_tokens == 3
    MockLLM.reset()


def test_openai_catalog_has_pricing() -> None:
    from agentgraph_llm.openai_compat import OpenAICompatLLM

    catalog = OpenAICompatLLM.CATALOG
    assert any(m.name == "gpt-4o" for m in catalog)
    assert all(m.input_cost_per_1k >= 0 for m in catalog)


def test_anthropic_catalog_has_pricing() -> None:
    from agentgraph_llm.anthropic import AnthropicLLM

    catalog = AnthropicLLM.CATALOG
    assert any("claude" in m.name for m in catalog)
