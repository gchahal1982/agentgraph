"""Build a custom graph from scratch (no vertical pack)."""
import asyncio

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue
from agentgraph_llm.base import LLMConfig
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.graph import Graph as SDKGraph
from agentgraph_sdk.runner import Runner


@tool(description="Add two numbers")
async def add(ctx: ToolContext, a: float, b: float) -> dict[str, JSONValue]:
    return {"sum": a + b}


async def main() -> None:
    agent = Agent(
        AgentConfig(
            name="math_agent",
            description="an agent that adds two numbers",
            system_prompt="You are a math agent. Use the `add` tool to add two numbers.",
            llm=LLMConfig(provider="mock", model="mock-1"),
            tools=[add],
            max_steps=2,
        )
    )
    g = SDKGraph("custom")
    g.add_agent(agent, entrypoint=True)

    result = await Runner().arun(g.compile(), input={"prompt": "What is 2+2?"})
    print("output:", result.output)
    print("cost_usd:", result.cost_usd)


if __name__ == "__main__":
    asyncio.run(main())
