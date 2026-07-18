"""Insurance tools: claims, policy lookup, risk scoring, adjuster assignment."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue


class ClaimStore(Protocol):
    def open(self, claim: dict[str, Any]) -> dict[str, Any]: ...
    def update(self, claim_id: str, **fields: Any) -> dict[str, Any]: ...
    def list_open(self) -> list[dict[str, Any]]: ...


class InMemoryClaimStore:
    def __init__(self) -> None:
        self._claims: dict[str, dict[str, Any]] = {}

    def open(self, claim: dict[str, Any]) -> dict[str, Any]:
        cid = claim.setdefault("id", f"clm_{len(self._claims) + 1:05d}")
        claim["status"] = claim.get("status", "open")
        self._claims[cid] = claim
        return claim

    def update(self, claim_id: str, **fields: Any) -> dict[str, Any]:
        t = self._claims.setdefault(claim_id, {"id": claim_id, "status": "open"})
        t.update(fields)
        return t

    def list_open(self) -> list[dict[str, Any]]:
        return [c for c in self._claims.values() if c.get("status") == "open"]


class PolicyStore(Protocol):
    def get(self, policy_id: str) -> dict[str, Any] | None: ...


class InMemoryPolicyStore:
    def __init__(self) -> None:
        self._policies: dict[str, dict[str, Any]] = {}

    def seed(self, policies: Iterable[dict[str, Any]]) -> None:
        for p in policies:
            self._policies[p["id"]] = p

    def get(self, policy_id: str) -> dict[str, Any] | None:
        return self._policies.get(policy_id)


_claims: ClaimStore = InMemoryClaimStore()
_policies: PolicyStore = InMemoryPolicyStore()


def set_claim_store(s: ClaimStore) -> None:
    global _claims
    _claims = s


def set_policy_store(s: PolicyStore) -> None:
    global _policies
    _policies = s


@tool(description="Open a new claim with structured details. Returns the claim id.")
async def open_claim(
    ctx: ToolContext,
    *,
    policy_id: str,
    loss_type: str,
    description: str,
    reported_at: str,
    estimated_amount_usd: float = 0.0,
) -> dict[str, JSONValue]:
    policy = _policies.get(policy_id)
    if policy is None:
        return {"error": "policy_not_found", "policy_id": policy_id}
    claim = _claims.open(
        {
            "policy_id": policy_id,
            "loss_type": loss_type,
            "description": description,
            "reported_at": reported_at,
            "estimated_amount_usd": estimated_amount_usd,
            "policy_holder": policy.get("holder"),
        }
    )
    return {"claim": claim}


@tool(description="Update fields on an existing claim (status, severity, adjuster, notes).")
async def update_claim(
    ctx: ToolContext, claim_id: str, **fields: JSONValue
) -> dict[str, JSONValue]:
    return {"claim": _claims.update(claim_id, **fields)}


@tool(
    description="Score a risk 0-100 (higher = riskier). Uses amount, loss_type, and prior claims."
)
async def score_risk(
    ctx: ToolContext,
    *,
    loss_type: str,
    estimated_amount_usd: float,
    prior_claims_count: int = 0,
    fraud_indicators: int = 0,
) -> dict[str, JSONValue]:
    score = 0.0
    score += min(estimated_amount_usd / 1000.0, 40)
    score += {"auto": 5, "property": 10, "liability": 25, "life": 30, "health": 15}.get(
        loss_type, 10
    )
    score += min(prior_claims_count * 5, 20)
    score += min(fraud_indicators * 15, 30)
    return {
        "score": int(min(score, 100)),
        "factors": {
            "amount": estimated_amount_usd,
            "type": loss_type,
            "prior_claims": prior_claims_count,
            "fraud_indicators": fraud_indicators,
        },
    }


@tool(description="Look up a policy by id. Returns holder, coverage, and exclusions.")
async def lookup_policy(ctx: ToolContext, policy_id: str) -> dict[str, JSONValue]:
    p = _policies.get(policy_id)
    return {"policy": p} if p else {"error": "not_found", "policy_id": policy_id}


@tool(description="Assign a claim to an adjuster. Adjusters are routed by loss type and severity.")
async def assign_adjuster(
    ctx: ToolContext, *, claim_id: str, adjuster_id: str, reason: str
) -> dict[str, JSONValue]:
    return {"claim": _claims.update(claim_id, adjuster_id=adjuster_id, assignment_reason=reason)}


@tool(
    description="Escalate a claim to a senior human underwriter. Signals transition out of the agent node."
)
async def escalate_to_human(
    ctx: ToolContext, *, claim_id: str, reason: str, priority: str = "normal"
) -> dict[str, JSONValue]:
    ctx.state["__goto__"] = "human_review"
    ctx.state["escalation"] = {"claim_id": claim_id, "reason": reason, "priority": priority}
    return {"escalated": True, "claim_id": claim_id, "reason": reason}
