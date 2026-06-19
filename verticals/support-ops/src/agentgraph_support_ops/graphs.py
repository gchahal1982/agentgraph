"""Support-ops graphs.

- `ticket_triage_graph`: canonical support flow
- `csat_loop_graph`: post-resolution CSAT analysis
"""
from __future__ import annotations

import os

from agentgraph_core.audit import AuditLog
from agentgraph_core.rbac import Principal
from agentgraph_llm.base import LLMConfig
from agentgraph_runtime.checkpoint import CheckpointStore
from agentgraph_runtime.node import END, NodeResult, node
from agentgraph_runtime.state import GraphState
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.runner import Runner

from agentgraph_support_ops.agents import CSAT_PROMPT, TRIAGE_PROMPT
from agentgraph_support_ops.tools import (
    escalate_to_human,
    kb_add_article,
    kb_search,
    sentiment_score,
    ticket_create,
    ticket_update,
)

DEFAULT_LLM = LLMConfig(
    provider=os.environ.get("AG_SUPPORT_LLM_PROVIDER", "mock"),
    model=os.environ.get("AG_SUPPORT_LLM_MODEL", "mock-1"),
)

TRIAGE_TOOLS = [kb_search, ticket_create, ticket_update, sentiment_score, escalate_to_human]


def build_triage_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="triage",
            description="Triage an incoming support ticket and route it.",
            system_prompt=TRIAGE_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=TRIAGE_TOOLS,
            max_steps=5,
        )
    )


def build_csat_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="csat_analyst",
            description="Score a closed ticket's CSAT and propose follow-ups.",
            system_prompt=CSAT_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=[kb_add_article],
            max_steps=3,
        )
    )


@node("intake")
async def intake_node(state: GraphState) -> NodeResult:
    """Normalize the inbound message and stash it on state."""
    msg = state.run.input.get("message")
    email = state.run.input.get("requester_email", "")
    if not msg:
        return NodeResult(error="message required", end=True)
    state.values["customer_message"] = msg
    state.values["requester_email"] = email
    return NodeResult(next="triage")


@node("triage")
async def triage_node(state: GraphState) -> NodeResult:
    """Wrapper node hosting the triage LLM agent."""
    return NodeResult(next="route_after_triage")


@node("route_after_triage")
async def route_after_triage(state: GraphState) -> NodeResult:
    """Route based on the triage agent's verdict in `state.values.triage`."""
    triage = state.values.get("triage", {}) or {}
    intent = triage.get("intent", "other")
    sentiment = float(triage.get("sentiment", 0.0) or 0.0)
    urgency = triage.get("urgency", "normal")
    if urgency == "urgent" or sentiment < -0.4:
        return NodeResult(next="escalate")
    if intent == "question" and state.values.get("kb_hit"):
        return NodeResult(next="deflect")
    return NodeResult(next="draft_reply")


@node("deflect")
async def deflect_node(state: GraphState) -> NodeResult:
    """Send the KB answer back to the customer (or to the agent to review)."""
    state.values["deflection"] = {
        "channel": "auto",
        "answer": state.values.get("kb_hit", {}).get("body", ""),
        "ticket_id": state.values.get("ticket_id"),
    }
    return NodeResult(end=True)


@node("draft_reply")
async def draft_reply_node(state: GraphState) -> NodeResult:
    """Wrapper node hosting the reply drafter (often the same agent)."""
    return NodeResult(next="await_human")


@node("await_human")
async def await_human_node(state: GraphState) -> NodeResult:
    state.values["awaiting_human_review"] = True
    return NodeResult(end=True)


@node("escalate")
async def escalate_node(state: GraphState) -> NodeResult:
    state.values["escalation_status"] = "queued"
    return NodeResult(end=True)


@node("csat_predict")
async def csat_predict_node(state: GraphState) -> NodeResult:
    return NodeResult(end=True)


def ticket_triage_graph(llm: LLMConfig | None = None) -> tuple:
    """Build the canonical support triage graph."""
    from agentgraph_sdk.graph import Graph as SDKGraph

    triage = build_triage_agent(llm)
    triage.config.name = "triage_agent"
    triage.node.spec.name = "triage_agent"
    triage.node.node.name = "triage_agent"
    g = SDKGraph("ticket_triage")
    g.add_node(intake_node)
    g.add_node(triage_node)
    g.add_node(route_after_triage)
    g.add_node(deflect_node)
    g.add_node(draft_reply_node)
    g.add_node(await_human_node)
    g.add_node(escalate_node)
    g.add_agent(triage, entrypoint=False)
    # Wire the wrapper to the agent's renamed node.
    g.add_edge("triage", "triage_agent")
    g.add_edge("intake", "triage")
    g.add_edge("triage_agent", "route_after_triage")
    g.add_edge("route_after_triage", "deflect")
    g.add_edge("route_after_triage", "draft_reply")
    g.add_edge("route_after_triage", "escalate")
    g.add_edge("draft_reply", "await_human")
    g.add_edge("deflect", END)
    g.add_edge("await_human", END)
    g.add_edge("escalate", END)
    g.set_entrypoint("intake")
    return g.compile(), {"triage": triage}


def csat_loop_graph(llm: LLMConfig | None = None) -> tuple:
    """Build a CSAT analysis graph for closed tickets."""
    from agentgraph_sdk.graph import Graph as SDKGraph

    csat = build_csat_agent(llm)
    g = SDKGraph("csat_loop")
    g.add_agent(csat, entrypoint=True)
    g.add_node(csat_predict_node)
    g.add_edge(csat.node.spec.name, "csat_predict")
    g.add_edge("csat_predict", END)
    return g.compile(), {"csat": csat}


def build_support_ops_runner(
    *,
    checkpoint_store: CheckpointStore | None = None,
    audit_log: AuditLog | None = None,
    principal: Principal | None = None,
    storage_url: str | None = None,
) -> Runner:
    return Runner(
        checkpoint_store=checkpoint_store,
        audit_log=audit_log,
        principal=principal,
        storage_url=storage_url,
    )
