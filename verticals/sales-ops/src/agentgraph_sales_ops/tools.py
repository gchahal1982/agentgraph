"""Sales-ops tools: CRM enrichment, lead scoring, outreach drafting.

These are real tool definitions, not stubs. They call into pluggable
backends (`crm_lookup` -> whatever you pass to the `CRM` constructor).
The default backend is in-memory and useful for local development and CI.
"""
from __future__ import annotations

import re
from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue


class CRM(Protocol):
    """A pluggable CRM backend. Implementations may wrap HubSpot, Salesforce,
    Pipedrive, or a local fixture for development."""

    def get(self, email: str | None = None, *, account_id: str | None = None) -> dict[str, Any] | None: ...
    def upsert(self, lead: dict[str, Any]) -> dict[str, Any]: ...
    def list_accounts(self) -> list[dict[str, Any]]: ...
    def activities(self, account_id: str, *, limit: int = 10) -> list[dict[str, Any]]: ...


class InMemoryCRM:
    """Local CRM fixture for development and tests."""

    def __init__(self) -> None:
        self._accounts: dict[str, dict[str, Any]] = {}
        self._by_email: dict[str, str] = {}  # email -> account_id
        self._activities: dict[str, list[dict[str, Any]]] = {}

    def seed(self, accounts: list[dict[str, Any]]) -> None:
        for a in accounts:
            aid = a.setdefault("id", a.get("domain", "acct_" + str(len(self._accounts))))
            self._accounts[aid] = a
            for c in a.get("contacts", []):
                self._by_email[c["email"].lower()] = aid
                self._activities.setdefault(aid, []).append(
                    {"type": "contact_added", "at": 0, "detail": c["email"]}
                )

    def get(self, email: str | None = None, *, account_id: str | None = None) -> dict[str, Any] | None:
        if email is not None:
            aid = self._by_email.get(email.lower())
            return self._accounts.get(aid) if aid else None
        if account_id is not None:
            return self._accounts.get(account_id)
        return None

    def upsert(self, lead: dict[str, Any]) -> dict[str, Any]:
        aid = lead.get("id") or lead.get("domain") or "lead_" + str(len(self._accounts))
        lead = {**lead, "id": aid}
        self._accounts[aid] = lead
        if "email" in lead:
            self._by_email[lead["email"].lower()] = aid
        self._activities.setdefault(aid, []).append(
            {"type": "lead_upserted", "at": 0, "detail": lead.get("email") or aid}
        )
        return lead

    def list_accounts(self) -> list[dict[str, Any]]:
        return list(self._accounts.values())

    def activities(self, account_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return list(self._activities.get(account_id, []))[-limit:]


# Singleton default; verticals typically inject their own.
_default_crm: CRM = InMemoryCRM()


def set_crm(crm: CRM) -> None:
    """Inject the CRM backend. Called by `SalesOpsService` or by tests."""
    global _default_crm
    _default_crm = crm


def get_crm() -> CRM:
    return _default_crm


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@tool(description="Look up a CRM account by email or account id.")
async def crm_lookup(
    ctx: ToolContext, email: str | None = None, account_id: str | None = None
) -> dict[str, JSONValue]:
    if email is None and account_id is None:
        return {"error": "must provide email or account_id"}
    if email is not None and not _EMAIL_RE.match(email):
        return {"error": f"invalid email: {email!r}"}
    acct = get_crm().get(email=email, account_id=account_id)
    if acct is None:
        return {"error": "not_found", "queried": {"email": email, "account_id": account_id}}
    return {"account": acct, "activities": get_crm().activities(acct["id"], limit=5)}


@tool(description="Upsert a lead into the CRM.")
async def crm_upsert(ctx: ToolContext, lead: dict[str, JSONValue]) -> dict[str, JSONValue]:
    if "email" not in lead or not _EMAIL_RE.match(str(lead["email"])):
        return {"error": "valid email required"}
    saved = get_crm().upsert(dict(lead))
    return {"saved": saved}


@tool(
    description=(
        "Score a lead on a 0-100 scale using a simple deterministic "
        "heuristic over firmographics and intent. The LLM agent can use "
        "this to anchor its judgment."
    )
)
async def score_lead(
    ctx: ToolContext,
    *,
    company_size: int = 0,
    industry: str = "",
    has_budget: bool = False,
    timeline_months: int = 0,
    is_referral: bool = False,
) -> dict[str, JSONValue]:
    score = 0
    score += min(company_size / 10, 30)  # up to 30 points for size
    if has_budget:
        score += 25
    if timeline_months and timeline_months <= 6:
        score += 20
    if industry.lower() in {"saas", "fintech", "healthtech"}:
        score += 10
    if is_referral:
        score += 15
    return {"score": int(score), "components": {"size": company_size, "industry": industry, "timeline_months": timeline_months}}


@tool(
    description=(
        "Draft a personalized cold-outreach email given a contact, account, "
        "and the angle to use. Returns subject + body."
    )
)
async def draft_email(
    ctx: ToolContext,
    *,
    contact_name: str,
    company: str,
    angle: str = "ROI",
    tone: str = "concise",
    word_limit: int = 120,
) -> dict[str, JSONValue]:
    subject = f"Quick idea for {company}'s {angle.lower()}"
    body = (
        f"Hi {contact_name.split()[0]},\n\n"
        f"I noticed {company} is scaling. We help similar teams hit "
        f"{angle} outcomes in weeks, not quarters. Worth a 15-minute call "
        f"next week?\n\n"
        f"- Sent via AgentGraph sales-ops"
    )
    return {
        "subject": subject,
        "body": body,
        "tone": tone,
        "word_limit": word_limit,
    }


@tool(description="Hand the lead off to a human sales rep; signals a transition out of the agent node.")
async def handoff_to_rep(
    ctx: ToolContext,
    *,
    rep_id: str,
    reason: str,
    priority: int = 5,
) -> dict[str, JSONValue]:
    """Set `__goto__` on the state so the runtime transitions out of the agent."""
    ctx.state["__goto__"] = "human_handoff"
    ctx.state["handoff"] = {
        "to": rep_id,
        "reason": reason,
        "priority": priority,
    }
    return {"status": "queued", "rep_id": rep_id, "reason": reason}
