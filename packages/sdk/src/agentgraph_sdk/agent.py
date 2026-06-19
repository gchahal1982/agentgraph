"""`Agent`: a one-node graph with an LLM and tools.

This is the convenience entry point for "I just want an agent". For
multi-step processes use `Graph` directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agentgraph_core.tools import Tool
from agentgraph_llm.base import LLM, LLMConfig, ToolSpec
from agentgraph_runtime.agent_node import AgentNode, AgentSpec


@dataclass(slots=True)
class AgentConfig:
    """Configuration for an `Agent`."""

    name: str
    description: str
    system_prompt: str
    llm: LLMConfig
    tools: list[Tool] = field(default_factory=list)
    max_steps: int = 8


class Agent:
    """A reusable agent definition.

    Wrap an agent in a `Graph` to compose it with other nodes; or call
    `Agent.invoke(prompt)` directly for a one-shot execution.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._spec = AgentSpec(
            name=config.name,
            description=config.description,
            system_prompt=config.system_prompt,
            tools=config.tools,
            llm=config.llm,
            max_steps=config.max_steps,
        )
        self._node = AgentNode(self._spec, _make_llm(config.llm))

    @property
    def node(self) -> AgentNode:
        return self._node

    @property
    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(name=t.name, description=t.description, parameters=t.args_schema)
            for t in self.config.tools
        ]


def _make_llm(cfg: LLMConfig) -> LLM:
    from agentgraph_llm.base import llm_for_config

    return llm_for_config(cfg)
