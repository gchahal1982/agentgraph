"""Sales-ops graphs.

Two graphs ship by default:

- `lead_qualification_graph` is the canonical sales-ops flow. It runs the
  enrichment, scoring, outreach, and handoff nodes in order, with a
  conditional edge that skips outreach for low-quality leads.

- `pipeline_summary_graph` is read-only: it summarizes recent CRM
  activity and proposes next-best-actions for an account.
"""
from __future__ import annotations

from agentgraph_core.audit import AuditLog
from agentgraph_core.rbac import Principal
from agentgraph_llm.base import LLMConfig
from agentgraph_runtime.checkpoint import CheckpointStore
from agentgraph_runtime.node import END, NodeResult, node
from agentgraph_runtime.state import GraphState
from agentgraph_sdk.agent import Agent, AgentConfig
from agentgraph_sdk.runner import Runner

from agentgraph_sales_ops.agents import OUTREACH_PROMPT, QUALIFIER_PROMPT, REVIEWER_PROMPT
from agentgraph_sales_ops.tools import (
    crm_lookup,
    crm_upsert,
    draft_email,
    handoff_to_rep,
    score_lead,
)


def _resolve_llm(llm: LLMConfig | None) -> LLMConfig:
    """Use the given LLM config, or resolve the process default (fail-fast)."""
    if llm is not None:
        return llm
    from agentgraph_llm.base import default_llm_config

    return default_llm_config()


QUALIFIER_TOOLS = [crm_lookup, crm_upsert, score_lead, handoff_to_rep]
OUTREACH_TOOLS = [crm_lookup, draft_email]


def build_qualifier_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="qualify_lead",
            description="Enrich the lead, score it, and decide MQL/SQL/disqualified.",
            system_prompt=QUALIFIER_PROMPT,
            llm=_resolve_llm(llm),
            tools=QUALIFIER_TOOLS,
            max_steps=4,
        )
    )


def build_outreach_agent(llm: LLMConfig | None = None) -> Agent:
    return Agent(
        AgentConfig(
            name="draft_outreach",
            description="Draft a personalized cold email for the lead.",
            system_prompt=OUTREACH_PROMPT,
            llm=_resolve_llm(llm),
            tools=OUTREACH_TOOLS,
            max_steps=3,
        )
    )


# --- node wrappers ---


@node("enrich")
async def enrich_node(state: GraphState) -> NodeResult:
    """Pull CRM data and stash the contact + account on state for later nodes."""
    user = state.run.input.get("contact_email")
    account = state.run.input.get("account_id")
    if not user and not account:
        return NodeResult(error="contact_email or account_id required", end=True)
    from agentgraph_sales_ops.tools import get_crm

    crm = get_crm()
    acct = crm.get(email=str(user)) if user else crm.get(account_id=str(account))
    state.values["account"] = acct or {}
    return NodeResult(next="score_and_qualify")


@node("score_and_qualify")
async def score_qualify_node(state: GraphState) -> NodeResult:
    """Wrapper node that runs the qualifier LLM agent and decides routing."""
    return NodeResult(next="route_after_qualify")


@node("route_after_qualify")
async def route_after_qualify(state: GraphState) -> NodeResult:
    """Decide: outreach, handoff, or end.

    Reads the qualifier agent's verdict from `state.values.qualification`
    and routes to the right next node.
    """
    verdict = state.values.get("qualification", {}) or {}
    bucket = verdict.get("bucket", "disqualified")
    if bucket == "sql":
        # Hot lead: hand off to a human rep.
        return NodeResult(next="human_handoff")
    if bucket == "mql":
        return NodeResult(next="draft_outreach")
    return NodeResult(end=True)


@node("draft_outreach")
async def draft_outreach_node(state: GraphState) -> NodeResult:
    """Run the outreach agent and persist the email to state."""
    return NodeResult(next="notify_rep")


@node("notify_rep")
async def notify_rep_node(state: GraphState) -> NodeResult:
    """Append a notification record (in real life, send an email or Slack msg)."""
    state.values["notification"] = {
        "channel": "email",
        "to": "sales-team@example.com",
        "subject": "New MQL drafted",
        "summary": state.values.get("drafted_email", {}).get("subject", ""),
    }
    return NodeResult(end=True)


@node("human_handoff")
async def human_handoff_node(state: GraphState) -> NodeResult:
    """Mark the run as paused; a separate worker drains the handoff queue."""
    state.values["handoff_status"] = "queued"
    return NodeResult(end=True)


# --- public graphs ---


def lead_qualification_graph(llm: LLMConfig | None = None) -> tuple:
    """Build the canonical lead-qualification graph.

    Returns `(graph, agents_dict)` so callers can register them with a
    service. The compiled graph is suitable for the `Runtime`.
    """
    from agentgraph_sdk.graph import Graph as SDKGraph

    qualifier = build_qualifier_agent(llm)
    outreach = build_outreach_agent(llm)
    qualifier.config.name = "qualifier_agent"
    qualifier.node.spec.name = "qualifier_agent"
    qualifier.node.node.name = "qualifier_agent"
    outreach.config.name = "outreach_agent"
    outreach.node.spec.name = "outreach_agent"
    outreach.node.node.name = "outreach_agent"

    g = SDKGraph("lead_qualification")
    g.add_node(enrich_node)
    g.add_node(score_qualify_node)
    g.add_node(route_after_qualify)
    g.add_node(draft_outreach_node)
    g.add_node(notify_rep_node)
    g.add_node(human_handoff_node)

    g.add_agent(qualifier, entrypoint=False)
    g.add_agent(outreach, entrypoint=False)

    g.add_edge("enrich", "score_and_qualify")
    g.add_edge("score_and_qualify", "qualifier_agent")
    g.add_edge("qualifier_agent", "route_after_qualify")
    g.add_edge("route_after_qualify", "draft_outreach")
    g.add_edge("route_after_qualify", "human_handoff")
    g.add_edge("route_after_qualify", END)
    g.add_edge("draft_outreach", "outreach_agent")
    g.add_edge("outreach_agent", "notify_rep")
    g.add_edge("notify_rep", END)
    g.add_edge("human_handoff", END)

    g.set_entrypoint("enrich")
    return g.compile(), {"qualifier": qualifier, "outreach": outreach}


def pipeline_summary_graph(llm: LLMConfig | None = None) -> tuple:
    """A read-only graph that summarizes an account's pipeline.

    Useful for the daily standup or for a sales rep to ask "what's the
    status of this account?".
    """
    from agentgraph_sdk.graph import Graph as SDKGraph

    reviewer = Agent(
        AgentConfig(
            name="pipeline_reviewer",
            description="Summarize an account's pipeline and propose next steps.",
            system_prompt=REVIEWER_PROMPT,
            llm=_resolve_llm(llm),
            tools=[crm_lookup],
        )
    )
    g = SDKGraph("pipeline_summary")
    g.add_agent(reviewer, entrypoint=True)
    return g.compile(), {"reviewer": reviewer}


def build_sales_ops_runner(
    *,
    checkpoint_store: CheckpointStore | None = None,
    audit_log: AuditLog | None = None,
    principal: Principal | None = None,
    storage_url: str | None = None,
) -> Runner:
    """A pre-configured `Runner` for sales-ops services."""
    return Runner(
        checkpoint_store=checkpoint_store,
        audit_log=audit_log,
        principal=principal,
        storage_url=storage_url,
    )
