"""Recruiting graphs."""
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

from agentgraph_recruiting.agents import SCREENING_PROMPT, SOURCING_PROMPT
from agentgraph_recruiting.tools import (
    draft_outreach,
    get_resume,
    handoff_to_recruiter,
    schedule_screen,
    score_candidate,
    search_candidates,
)

DEFAULT_LLM = LLMConfig(
    provider=os.environ.get("AG_RECRUITING_LLM_PROVIDER", "mock"),
    model=os.environ.get("AG_RECRUITING_LLM_MODEL", "mock-1"),
)

SOURCING_TOOLS = [
    search_candidates,
    get_resume,
    score_candidate,
    draft_outreach,
    schedule_screen,
    handoff_to_recruiter,
]


def build_sourcing_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="sourcer",
            description="Source and outreach candidates for an open role.",
            system_prompt=SOURCING_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=SOURCING_TOOLS,
            max_steps=8,
        )
    )


def build_screening_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="screener",
            description="Screen a single candidate's resume against a role.",
            system_prompt=SCREENING_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=[get_resume, score_candidate, draft_outreach, schedule_screen, handoff_to_recruiter],
            max_steps=4,
        )
    )


@node("parse_role")
async def parse_role_node(state: GraphState) -> NodeResult:
    role = state.run.input.get("role_title", "Software Engineer")
    skills = state.run.input.get("required_skills", [])
    years = state.run.input.get("years_experience", 3)
    state.values["role_title"] = role
    state.values["required_skills"] = skills
    state.values["years_experience"] = years
    return NodeResult(next="source")


@node("source")
async def source_node(state: GraphState) -> NodeResult:
    return NodeResult(next="draft_outreach")


@node("draft_outreach")
async def draft_outreach_node(state: GraphState) -> NodeResult:
    return NodeResult(next="handoff")


@node("handoff")
async def handoff_node(state: GraphState) -> NodeResult:
    state.values["recruiter_handoff_status"] = "queued"
    return NodeResult(end=True)


def candidate_sourcing_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    sourcer = build_sourcing_agent(llm)
    g = SDKGraph("candidate_sourcing")
    g.add_node(parse_role_node)
    g.add_node(source_node)
    g.add_node(draft_outreach_node)
    g.add_node(handoff_node)
    g.add_agent(sourcer, entrypoint=False)
    g.add_edge("parse_role", "source")
    g.add_edge("source", "draft_outreach")
    g.add_edge("draft_outreach", "handoff")
    g.add_edge("handoff", END)
    g.set_entrypoint("parse_role")
    return g.compile(), {"sourcer": sourcer}


def candidate_screening_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    screener = build_screening_agent(llm)
    g = SDKGraph("candidate_screening")
    g.add_agent(screener, entrypoint=True)
    return g.compile(), {"screener": screener}


def build_recruiting_runner(
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
