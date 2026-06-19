"""SDK: Agent, Graph, Runner."""
from __future__ import annotations

import pytest

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue, ToolCall
from agentgraph_llm.base import LLMConfig
from agentgraph_llm.testing import ScriptedLLM, register_test_provider, response
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.graph import Graph as SDKGraph
from agentgraph_sdk.runner import Runner


def setup_module() -> None:
    register_test_provider()


@tool(description="Get the current weather")
async def get_weather(ctx: ToolContext, city: str = "SF") -> dict[str, JSONValue]:
    return {"city": city, "temp_f": 64, "condition": "foggy"}


@pytest.mark.asyncio
async def test_agent_invokes_llm_and_tools() -> None:
    register_test_provider()
    ScriptedLLM.reset()
    ScriptedLLM.script(
        "weather_agent",
        response(
            text="",
            tool_calls=[
                ToolCall(id="call_1", name="get_weather", arguments={"city": "Berkeley"}),
            ],
            prompt_tokens=10,
            completion_tokens=5,
        ),
        response(text="It's 64F and foggy in Berkeley.", prompt_tokens=12, completion_tokens=8),
    )
    cfg = AgentConfig(
        name="weather_agent",
        description="weather",
        system_prompt="you are a weather agent",
        llm=LLMConfig(provider="test", model="test-model"),
        tools=[get_weather],
        max_steps=4,
    )
    agent = Agent(cfg)

    g = SDKGraph("weather_test")
    g.add_agent(agent, entrypoint=True)
    compiled = g.compile()
    result = await Runner().arun(compiled, input={"prompt": "What's the weather in Berkeley?"})
    assert result.finished
    assert result.state.values.get("total_tokens", 0) >= 0
    ScriptedLLM.reset()


@pytest.mark.asyncio
async def test_runner_records_cost() -> None:
    register_test_provider()
    ScriptedLLM.reset()
    ScriptedLLM.script("cheap", response(text="done", prompt_tokens=100, completion_tokens=50))
    cfg = AgentConfig(
        name="cheap",
        description="cheap agent",
        system_prompt="you are cheap",
        llm=LLMConfig(provider="test", model="test-model"),
    )
    agent = Agent(cfg)
    g = SDKGraph("cost_test").add_agent(agent, entrypoint=True)
    compiled = g.compile()
    result = await Runner().arun(compiled, input={"prompt": "hi"})
    assert result.cost_usd >= 0
    assert result.tokens >= 0
    ScriptedLLM.reset()
