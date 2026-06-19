"""Insurance graphs."""
from __future__ import annotations

import os

from agentgraph_core.audit import AuditLog, InMemoryAuditLog
from agentgraph_core.rbac import Principal
from agentgraph_llm.base import LLMConfig
from agentgraph_runtime.checkpoint import CheckpointStore, InMemoryCheckpointStore
from agentgraph_runtime.node import END, NodeResult, node
from agentgraph_runtime.state import GraphState
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.runner import Runner

from agentgraph_insurance.agents import CLAIMS_TRIAGE_PROMPT, FNOL_PROMPT, UNDERWRITING_PROMPT
from agentgraph_insurance.tools import (
    assign_adjuster,
    escalate_to_human,
    lookup_policy,
    open_claim,
    score_risk,
    update_claim,
)

DEFAULT_LLM = LLMConfig(
    provider=os.environ.get("AG_INSURANCE_LLM_PROVIDER", "mock"),
    model=os.environ.get("AG_INSURANCE_LLM_MODEL", "mock-1"),
)

FNOL_TOOLS = [lookup_policy, open_claim, score_risk, assign_adjuster, escalate_to_human]
UNDERWRITING_TOOLS = [lookup_policy, score_risk, escalate_to_human]
CLAIMS_TRIAGE_TOOLS = [update_claim, score_risk, assign_adjuster, escalate_to_human]


def build_fnol_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="fnol_intake",
            description="Capture FNOL and route to the right adjuster.",
            system_prompt=FNOL_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=FNOL_TOOLS,
            max_steps=6,
        )
    )


def build_underwriting_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="underwriting_copilot",
            description="Score risk and recommend accept/conditional/decline.",
            system_prompt=UNDERWRITING_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=UNDERWRITING_TOOLS,
            max_steps=4,
        )
    )


def build_claims_triage_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="claims_triage",
            description="Triage a batch of open claims and assign adjusters.",
            system_prompt=CLAIMS_TRIAGE_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=CLAIMS_TRIAGE_TOOLS,
            max_steps=6,
        )
    )


@node("intake")
async def intake_node(state: GraphState) -> NodeResult:
    description = state.run.input.get("description", "")
    if not description:
        return NodeResult(error="description required", end=True)
    state.values["customer_description"] = description
    return NodeResult(next="fnol")


@node("fnol")
async def fnol_node(state: GraphState) -> NodeResult:
    return NodeResult(next="route_after_fnol")


@node("route_after_fnol")
async def route_after_fnol(state: GraphState) -> NodeResult:
    risk = state.values.get("risk", {}) or {}
    if int(risk.get("score", 0)) >= 70:
        return NodeResult(next="human_review")
    if state.values.get("claim"):
        return NodeResult(next="END")
    return NodeResult(next="human_review")


@node("human_review")
async def human_review_node(state: GraphState) -> NodeResult:
    state.values["awaiting_human_review"] = True
    return NodeResult(end=True)


def fnol_intake_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    fnol = build_fnol_agent(llm)
    fnol.config.name = "fnol_agent"
    fnol.node.spec.name = "fnol_agent"
    fnol.node.node.name = "fnol_agent"
    g = SDKGraph("fnol_intake")
    g.add_node(intake_node)
    g.add_node(fnol_node)
    g.add_node(route_after_fnol)
    g.add_node(human_review_node)
    g.add_agent(fnol, entrypoint=False)
    g.add_edge("intake", "fnol")
    g.add_edge("fnol", "fnol_agent")
    g.add_edge("fnol_agent", "route_after_fnol")
    g.add_edge("route_after_fnol", "human_review")
    g.add_edge("route_after_fnol", END)
    g.add_edge("human_review", END)
    g.set_entrypoint("intake")
    return g.compile(), {"fnol": fnol}


def underwriting_copilot_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    uw = build_underwriting_agent(llm)
    g = SDKGraph("underwriting_copilot")
    g.add_agent(uw, entrypoint=True)
    return g.compile(), {"underwriter": uw}


def claims_triage_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    triage = build_claims_triage_agent(llm)
    g = SDKGraph("claims_triage")
    g.add_agent(triage, entrypoint=True)
    return g.compile(), {"triage": triage}


def build_insurance_runner(
    *,
    checkpoint_store: CheckpointStore | None = None,
    audit_log: AuditLog | None = None,
    principal: Principal | None = None,
) -> Runner:
    return Runner(
        checkpoint_store=checkpoint_store or InMemoryCheckpointStore(),
        audit_log=audit_log or InMemoryAuditLog(),
        principal=principal,
    )
