"""Healthcare graphs."""
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

from agentgraph_healthcare.agents import DISCHARGE_PROMPT, INTAKE_PROMPT, PRIOR_AUTH_PROMPT
from agentgraph_healthcare.tools import (
    append_discharge_summary,
    draft_prior_auth,
    escalate_to_clinician,
    lookup_patient,
    open_encounter,
    signoff_prior_auth,
)

DEFAULT_LLM = LLMConfig(
    provider=os.environ.get("AG_HEALTHCARE_LLM_PROVIDER", "mock"),
    model=os.environ.get("AG_HEALTHCARE_LLM_MODEL", "mock-1"),
)


def build_intake_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="intake_triage",
            description="Triage a patient intake message by acuity.",
            system_prompt=INTAKE_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=[lookup_patient, open_encounter, escalate_to_clinician],
            max_steps=4,
        )
    )


def build_prior_auth_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="prior_auth",
            description="Draft a prior-authorization request from a clinical note.",
            system_prompt=PRIOR_AUTH_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=[lookup_patient, draft_prior_auth, signoff_prior_auth, escalate_to_clinician],
            max_steps=4,
        )
    )


def build_discharge_agent(llm: LLMConfig | None = None):

    return Agent(
        AgentConfig(
            name="discharge_summary",
            description="Compose a discharge summary from a hospital-stay transcript.",
            system_prompt=DISCHARGE_PROMPT,
            llm=llm or DEFAULT_LLM,
            tools=[append_discharge_summary, lookup_patient],
            max_steps=3,
        )
    )


@node("intake")
async def intake_node(state: GraphState) -> NodeResult:
    message = state.run.input.get("message", "")
    patient_id = state.run.input.get("patient_id", "")
    if not message or not patient_id:
        return NodeResult(error="message and patient_id required", end=True)
    state.values["patient_message"] = message
    state.values["patient_id"] = patient_id
    return NodeResult(next="triage")


@node("triage")
async def triage_node(state: GraphState) -> NodeResult:
    return NodeResult(next="route_after_triage")


@node("route_after_triage")
async def route_after_triage(state: GraphState) -> NodeResult:
    acuity = state.values.get("acuity", "routine")
    if acuity in ("urgent", "emergent"):
        return NodeResult(next="clinician_review")
    return NodeResult(end=True)


@node("clinician_review")
async def clinician_review_node(state: GraphState) -> NodeResult:
    state.values["awaiting_clinician"] = True
    return NodeResult(end=True)


def intake_triage_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    intake = build_intake_agent(llm)
    intake.config.name = "intake_agent"
    intake.node.spec.name = "intake_agent"
    intake.node.node.name = "intake_agent"
    g = SDKGraph("intake_triage")
    g.add_node(intake_node)
    g.add_node(triage_node)
    g.add_node(route_after_triage)
    g.add_node(clinician_review_node)
    g.add_agent(intake, entrypoint=False)
    g.add_edge("intake", "triage")
    g.add_edge("triage", "intake_agent")
    g.add_edge("intake_agent", "route_after_triage")
    g.add_edge("route_after_triage", "clinician_review")
    g.add_edge("route_after_triage", END)
    g.add_edge("clinician_review", END)
    g.set_entrypoint("intake")
    return g.compile(), {"intake": intake}


def prior_auth_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    pa = build_prior_auth_agent(llm)
    g = SDKGraph("prior_auth")
    g.add_agent(pa, entrypoint=True)
    return g.compile(), {"prior_auth": pa}


def discharge_summary_graph(llm: LLMConfig | None = None) -> tuple:
    from agentgraph_sdk.graph import Graph as SDKGraph

    dc = build_discharge_agent(llm)
    g = SDKGraph("discharge_summary")
    g.add_agent(dc, entrypoint=True)
    return g.compile(), {"discharge": dc}


def build_healthcare_runner(
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
