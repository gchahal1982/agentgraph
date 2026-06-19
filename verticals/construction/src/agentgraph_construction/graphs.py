"""Construction graphs."""
from __future__ import annotations

from agentgraph_core.audit import AuditLog
from agentgraph_core.rbac import Principal
from agentgraph_llm.base import LLMConfig, default_llm_config
from agentgraph_runtime.checkpoint import CheckpointStore
from agentgraph_runtime.node import END, NodeResult, node
from agentgraph_runtime.state import GraphState
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.runner import Runner

from agentgraph_construction.agents import DAILY_LOG_PROMPT, RFI_PROMPT, SUBMITTAL_PROMPT
from agentgraph_construction.tools import (
    append_daily_log,
    create_rfi,
    escalate_to_pm,
    list_specs,
    lookup_project,
    review_submittal,
)


def _resolve_llm(llm: LLMConfig | None) -> LLMConfig:
    """Use the given LLM config, or resolve the process default (fail-fast)."""
    return llm if llm is not None else default_llm_config()


def build_rfi_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="rfi_drafter",
            description="Draft a structured RFI from field notes.",
            system_prompt=RFI_PROMPT,
            llm=_resolve_llm(llm),
            tools=[lookup_project, list_specs, create_rfi, escalate_to_pm],
            max_steps=5,
        )
    )


def build_submittal_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="submittal_reviewer",
            description="Review a submittal against the project spec.",
            system_prompt=SUBMITTAL_PROMPT,
            llm=_resolve_llm(llm),
            tools=[list_specs, review_submittal, escalate_to_pm],
            max_steps=4,
        )
    )


def build_daily_log_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="daily_log",
            description="Compose the daily log from crew inputs and weather.",
            system_prompt=DAILY_LOG_PROMPT,
            llm=_resolve_llm(llm),
            tools=[append_daily_log],
            max_steps=2,
        )
    )


@node("intake")
async def rfi_intake_node(state: GraphState) -> NodeResult:
    notes = state.run.input.get("field_notes", "")
    if not notes:
        return NodeResult(error="field_notes required", end=True)
    state.values["field_notes"] = notes
    return NodeResult(next="draft_rfi")


@node("draft_rfi")
async def draft_rfi_node(state: GraphState) -> NodeResult:
    return NodeResult(next="pm_review")


@node("pm_review")
async def pm_review_node(state: GraphState) -> NodeResult:
    state.values["rfi_pm_review_status"] = "queued"
    return NodeResult(end=True)


def rfi_drafting_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    rfi = build_rfi_agent(llm)
    rfi.config.name = "rfi_agent"
    rfi.node.spec.name = "rfi_agent"
    rfi.node.node.name = "rfi_agent"
    g = SDKGraph("rfi_drafting")
    g.add_node(rfi_intake_node)
    g.add_node(draft_rfi_node)
    g.add_node(pm_review_node)
    g.add_agent(rfi, entrypoint=False)
    g.add_edge("intake", "draft_rfi")
    g.add_edge("draft_rfi", "rfi_agent")
    g.add_edge("rfi_agent", "pm_review")
    g.add_edge("pm_review", END)
    g.set_entrypoint("intake")
    return g.compile(), {"rfi": rfi}


def submittal_review_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    sub = build_submittal_agent(llm)
    g = SDKGraph("submittal_review")
    g.add_agent(sub, entrypoint=True)
    return g.compile(), {"submittal": sub}


def daily_log_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    dl = build_daily_log_agent(llm)
    g = SDKGraph("daily_log")
    g.add_agent(dl, entrypoint=True)
    return g.compile(), {"daily_log": dl}


def build_construction_runner(
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
