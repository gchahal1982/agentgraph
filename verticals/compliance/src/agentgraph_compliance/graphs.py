"""Compliance graphs.

- `policy_review_graph`: review and sign off on a single control
- `audit_report_graph`:  generate a full audit report for a framework
"""
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

from agentgraph_compliance.agents import AUDIT_REPORT_PROMPT, POLICY_REVIEW_PROMPT
from agentgraph_compliance.tools import (
    attach_evidence,
    fetch_evidence,
    flag_risk,
    list_controls,
    signoff,
)

DEFAULT_LLM = LLMConfig(
    provider=os.environ.get("AG_COMPLIANCE_LLM_PROVIDER", "mock"),
    model=os.environ.get("AG_COMPLIANCE_LLM_MODEL", "mock-1"),
)

REVIEW_TOOLS = [fetch_evidence, list_controls, attach_evidence, flag_risk, signoff]


def build_review_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="policy_reviewer",
            description="Review and sign off on a control after collecting evidence.",
            system_prompt=POLICY_REVIEW_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=REVIEW_TOOLS,
            max_steps=8,
        )
    )


def build_audit_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="audit_report",
            description="Generate an audit-ready report for a framework.",
            system_prompt=AUDIT_REPORT_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=[fetch_evidence, list_controls, attach_evidence, flag_risk],
            max_steps=10,
        )
    )


@node("parse_request")
async def parse_request_node(state: GraphState) -> NodeResult:
    state.values["framework"] = state.run.input.get("framework", "soc2")
    state.values["control"] = state.run.input.get("control", "")
    state.values["date_range"] = state.run.input.get("date_range", "last_90_days")
    if not state.values["control"]:
        return NodeResult(error="control required", end=True)
    return NodeResult(next="collect_evidence")


@node("collect_evidence")
async def collect_evidence_node(state: GraphState) -> NodeResult:
    """Stubs an evidence pull; the LLM agent will do the real work."""
    return NodeResult(next="gap_analysis")


@node("gap_analysis")
async def gap_analysis_node(state: GraphState) -> NodeResult:
    return NodeResult(next="human_signoff")


@node("human_signoff")
async def human_signoff_node(state: GraphState) -> NodeResult:
    state.values["awaiting_signoff"] = True
    return NodeResult(end=True)


def policy_review_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    reviewer = build_review_agent(llm)
    reviewer.config.name = "reviewer_agent"
    reviewer.node.spec.name = "reviewer_agent"
    reviewer.node.node.name = "reviewer_agent"
    g = SDKGraph("policy_review")
    g.add_node(parse_request_node)
    g.add_node(collect_evidence_node)
    g.add_node(gap_analysis_node)
    g.add_node(human_signoff_node)
    g.add_agent(reviewer, entrypoint=False)
    g.add_edge("parse_request", "collect_evidence")
    g.add_edge("collect_evidence", "gap_analysis")
    g.add_edge("gap_analysis", "reviewer_agent")
    g.add_edge("reviewer_agent", "human_signoff")
    g.add_edge("human_signoff", END)
    g.set_entrypoint("parse_request")
    return g.compile(), {"reviewer": reviewer}


def audit_report_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    auditor = build_audit_agent(llm)
    g = SDKGraph("audit_report")
    g.add_agent(auditor, entrypoint=True)
    return g.compile(), {"auditor": auditor}


def build_compliance_runner(
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
