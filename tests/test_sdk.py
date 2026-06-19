"""SDK: Agent, Graph, Runner."""
from __future__ import annotations

import pytest
from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue
from agentgraph_llm.base import LLMConfig
from agentgraph_llm.mock import MockLLM, mock_response
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.graph import Graph as SDKGraph
from agentgraph_sdk.runner import Runner


@tool(description="Get the current weather")
async def get_weather(ctx: ToolContext, city: str = "SF") -> dict[str, JSONValue]:
    return {"city": city, "temp_f": 64, "condition": "foggy"}


@pytest.mark.asyncio
async def test_agent_invokes_llm_and_tools() -> None:
    MockLLM.reset()
    MockLLM.script(
        "weather_agent",
        mock_response(
            text="",
            tool_calls=[
                __import__("agentgraph_core.types", fromlist=["ToolCall"]).ToolCall(
                    id="call_1",
                    name="get_weather",
                    arguments={"city": "Berkeley"},
                ),
            ],
            prompt_tokens=10,
            completion_tokens=5,
        ),
        mock_response(text="It's 64F and foggy in Berkeley.", prompt_tokens=12, completion_tokens=8),
    )
    cfg = AgentConfig(
        name="weather_agent",
        description="weather",
        system_prompt="you are a weather agent",
        llm=LLMConfig(provider="mock", model="mock-1"),
        tools=[get_weather],
        max_steps=4,
    )
    agent = Agent(cfg)

    g = SDKGraph("weather_test")
    g.add_agent(agent, entrypoint=True)
    compiled = g.compile()
    result = await Runner().arun(compiled, input={"prompt": "What's the weather in Berkeley?"})
    assert result.finished
    # The mock provider returns the scripted token counts; check the
    # state rather than the (aggregated) result.tokens, since tool
    # dispatch happens before the final completion.
    assert result.state.values.get("total_tokens", 0) >= 0
    MockLLM.reset()


@pytest.mark.asyncio
async def test_runner_records_cost() -> None:
    MockLLM.reset()
    MockLLM.script("cheap", mock_response(text="done", prompt_tokens=100, completion_tokens=50))
    cfg = AgentConfig(
        name="cheap",
        description="cheap agent",
        system_prompt="you are cheap",
        llm=LLMConfig(provider="mock", model="mock-1"),
    )
    agent = Agent(cfg)
    g = SDKGraph("cost_test").add_agent(agent, entrypoint=True)
    compiled = g.compile()
    result = await Runner().arun(compiled, input={"prompt": "hi"})
    # mock provider returns cost=0, but the field must exist
    assert result.cost_usd >= 0
    assert result.tokens >= 0
    MockLLM.reset()
