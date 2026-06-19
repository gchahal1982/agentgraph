"""`AgentNode`: a node that calls an LLM with tools.

This is the workhorse of most graphs: assemble messages from state, call
the LLM, dispatch any tool calls, and merge the result. Vertical packs
ship `AgentSpec`s for their roles (sales rep, support agent, etc.).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from agentgraph_core.tools import Tool, ToolContext
from agentgraph_core.types import (
    Message,
    ModelResponse,
    Role,
    ToolResult,
)
from agentgraph_llm.base import LLM, LLMConfig, ToolSpec

from agentgraph_runtime.node import Node, NodeResult
from agentgraph_runtime.state import GraphState


@dataclass(slots=True)
class AgentSpec:
    """Configuration for a single `AgentNode`."""

    name: str
    description: str
    system_prompt: str
    tools: list[Tool] = field(default_factory=list)
    llm: LLMConfig | None = None
    # Number of LLM/tool round-trips to allow before forcing an exit.
    max_steps: int = 8
    # If True, when the model emits no tool calls, the node ends.
    end_on_no_tool_calls: bool = True
    # Optional user message template. Receives the current state.
    prompt_from_state: Callable[[GraphState], str] | None = None


class AgentNode:
    """A node that runs a tool-using LLM agent.

    The runtime calls `run(state)`. The node assembles a system prompt +
    user message + any prior messages, calls the LLM, and dispatches any
    tool calls. It loops until the model stops calling tools, `max_steps`
    is hit, or a tool signals a handoff (returning a `NodeResult` with
    `goto` set).
    """

    def __init__(self, spec: AgentSpec, llm: LLM | None = None) -> None:
        self.spec = spec
        self.llm = llm
        self._node = Node(name=spec.name, description=spec.description, handler=self.run)

    @property
    def node(self) -> Node:
        return self._node

    async def run(self, state: GraphState) -> NodeResult:
        from agentgraph_llm.base import (  # local import to avoid cycles
            default_llm_config,
            llm_for_config,
        )

        llm = self.llm
        if llm is None:
            cfg = self.spec.llm or default_llm_config()
            llm = llm_for_config(cfg)
        elif self.spec.llm is not None:
            llm = llm_for_config(self.spec.llm)

        tool_specs = [ToolSpec(name=t.name, description=t.description, parameters=t.args_schema) for t in self.spec.tools]
        tool_map = {t.name: t for t in self.spec.tools}

        # Compose the prompt from spec + state.
        messages: list[Message] = [Message(role=Role.SYSTEM, content=self.spec.system_prompt)]
        messages.extend(state.messages)
        if self.spec.prompt_from_state is not None:
            user_prompt = self.spec.prompt_from_state(state)
        else:
            user_prompt = state.get("input", "") or state.get("prompt", "") or ""
        if user_prompt:
            messages.append(Message(role=Role.USER, content=str(user_prompt)))

        ctx = ToolContext(
            run_id=state.run.run_id,
            thread_id=state.run.thread_id,
            principal_id=state.run.principal_id,
            state=state.values,
        )

        total_cost = 0.0
        total_tokens = 0

        for _step in range(self.spec.max_steps):
            response: ModelResponse = await llm.complete(messages, tools=tool_specs or None)
            total_cost += response.usage.cost_usd
            total_tokens += response.usage.total_tokens

            text = response.text or ""
            assistant_msg = Message(
                role=Role.ASSISTANT,
                content=text,
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_msg)
            state.add_message(assistant_msg)
            state.values["last_assistant_text"] = text
            state.values["last_finish_reason"] = response.finish_reason
            state.values["total_cost_usd"] = state.values.get("total_cost_usd", 0.0) + response.usage.cost_usd
            state.values["total_tokens"] = state.values.get("total_tokens", 0) + response.usage.total_tokens

            if not response.tool_calls:
                if self.spec.end_on_no_tool_calls:
                    state.values["agent_output"] = text
                    return NodeResult(end=True, updates={}, messages=[])
                # Otherwise we just continue; the graph builder should have
                # wired a conditional edge from this node.
                return NodeResult(next=None, updates={})

            # Dispatch tool calls in order. A tool can return a `NodeResult`
            # via a special key in its state to force a transition.
            for call in response.tool_calls:
                tool = tool_map.get(call.name)
                if tool is None:
                    result = ToolResult(
                        tool_call_id=call.id,
                        name=call.name,
                        content="",
                        error=f"Unknown tool {call.name!r}",
                    )
                else:
                    result = await tool(ctx, **call.arguments)
                    result.tool_call_id = call.id
                tool_msg = Message(
                    role=Role.TOOL,
                    name=call.name,
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                )
                if result.error:
                    tool_msg.metadata["error"] = result.error
                messages.append(tool_msg)
                state.add_message(tool_msg)

                # Tools can return a `handoff` key in their state to force
                # a transition out of the agent loop. This is the supported
                # way to do "human handoff" or "escalate" from a tool.
                if isinstance(ctx.state.get("__goto__"), str):
                    target = ctx.state.pop("__goto__")
                    return NodeResult(goto=[target], updates={}, messages=[])

        # Hit max_steps without an end condition.
        state.values.setdefault("agent_output", state.values.get("last_assistant_text", ""))
        return NodeResult(end=True, updates={})
