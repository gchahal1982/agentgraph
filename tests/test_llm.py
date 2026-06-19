"""LLM provider abstraction: registry, dispatch, default config."""
from __future__ import annotations

import pytest
from agentgraph_core.types import Message, Role
from agentgraph_llm.base import LLMConfig, default_llm_config, registry
from agentgraph_llm.testing import ScriptedLLM, register_test_provider, response


def setup_module() -> None:
    register_test_provider()


def test_registry_includes_builtins() -> None:
    r = registry()
    assert "openai" in r
    assert "anthropic" in r
    assert "ollama" in r


def test_test_provider_not_registered_by_default() -> None:
    # The scripted provider lives in agentgraph_llm.testing and must be
    # opt-in. Importing the package alone must not register it.
    import importlib

    mod = importlib.import_module("agentgraph_llm")
    assert "test" not in getattr(mod, "__all__", [])


@pytest.mark.asyncio
async def test_test_llm_returns_default() -> None:
    register_test_provider()
    ScriptedLLM.reset()
    llm = ScriptedLLM(LLMConfig(provider="test", model="test-model"))
    resp = await llm.complete([Message(role=Role.USER, content="hello")])
    assert resp.text == ""
    ScriptedLLM.reset()


@pytest.mark.asyncio
async def test_test_llm_scripted() -> None:
    register_test_provider()
    ScriptedLLM.reset()
    ScriptedLLM.script("greet", response(text="hi there", prompt_tokens=10, completion_tokens=3))
    llm = ScriptedLLM(LLMConfig(provider="test", model="test-model"))
    resp = await llm.complete([Message(role=Role.USER, content="please greet")])
    assert resp.text == "hi there"
    assert resp.usage.completion_tokens == 3
    ScriptedLLM.reset()


def test_default_llm_config_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AG_LLM_PROVIDER", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        default_llm_config()


def test_default_llm_config_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("AG_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AG_LLM_MODEL", raising=False)
    cfg = default_llm_config()
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"


def test_default_llm_config_ollama_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AG_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("AG_LLM_MODEL", raising=False)
    cfg = default_llm_config()
    assert cfg.provider == "ollama"
    assert cfg.model == "llama3.3"


def test_openai_catalog_has_pricing() -> None:
    from agentgraph_llm.openai_compat import OpenAICompatLLM

    catalog = OpenAICompatLLM.CATALOG
    assert any(m.name == "gpt-4o" for m in catalog)
    assert all(m.input_cost_per_1k >= 0 for m in catalog)


def test_anthropic_catalog_has_pricing() -> None:
    from agentgraph_llm.anthropic import AnthropicLLM

    catalog = AnthropicLLM.CATALOG
    assert any("claude" in m.name for m in catalog)
