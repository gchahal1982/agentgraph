"""Build a custom graph from scratch (no vertical pack).

    uv run --all-packages python examples/custom_graph.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import example_llm
from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue
from agentgraph_llm.base import LLMConfig, default_llm_config
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.graph import Graph as SDKGraph
from agentgraph_sdk.runner import Runner


@tool(description="Add two numbers")
async def add(ctx: ToolContext, a: float, b: float) -> dict[str, JSONValue]:
    return {"sum": a + b}


async def main() -> None:
    cfg = example_llm()
    if cfg.get("llm_provider"):
        llm = LLMConfig(provider=cfg["llm_provider"], model=cfg["llm_model"])
    else:
        llm = default_llm_config()
    agent = Agent(
        AgentConfig(
            name="math_agent",
            description="an agent that adds two numbers",
            system_prompt="You are a math agent. Use the `add` tool to add two numbers.",
            llm=llm,
            tools=[add],
            max_steps=2,
        )
    )
    g = SDKGraph("custom")
    g.add_agent(agent, entrypoint=True)
    result = await Runner(storage_url="memory://").arun(
        g.compile(), input={"prompt": "What is 2+2?"}
    )
    print("output:", result.output)
    print("cost_usd:", result.cost_usd)


if __name__ == "__main__":
    asyncio.run(main())
