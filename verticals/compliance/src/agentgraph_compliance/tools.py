"""Compliance tools: evidence collection, control mapping, risk flagging."""
from __future__ import annotations

from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue


class EvidenceStore(Protocol):
    def list(self, control: str) -> list[dict[str, Any]]: ...
    def attach(self, control: str, evidence: dict[str, Any]) -> dict[str, Any]: ...


class InMemoryEvidenceStore:
    """Local evidence store. Production deployments wire this to Vanta,
    Drata, or your GRC system of record."""

    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {}

    def seed(self, framework: str, controls: list[dict[str, Any]]) -> None:
        for c in controls:
            self._store[f"{framework}:{c['id']}"] = c.get("evidence", [])

    def list(self, control: str) -> list[dict[str, Any]]:
        return list(self._store.get(control, []))

    def attach(self, control: str, evidence: dict[str, Any]) -> dict[str, Any]:
        self._store.setdefault(control, []).append(evidence)
        return evidence


_store: EvidenceStore = InMemoryEvidenceStore()


def set_store(store: EvidenceStore) -> None:
    global _store
    _store = store


@tool(description="List evidence attached to a control id (e.g. 'soc2:CC6.1').")
async def list_controls(ctx: ToolContext, control: str) -> dict[str, JSONValue]:
    return {"control": control, "evidence": _store.list(control)}


@tool(description="Fetch a single piece of evidence from the connected source by id.")
async def fetch_evidence(ctx: ToolContext, evidence_id: str, source: str = "grc") -> dict[str, JSONValue]:
    # In production this would call into AWS Config, GitHub, GCP IAM, etc.
    return {
        "id": evidence_id,
        "source": source,
        "fetched": True,
        "summary": f"Evidence {evidence_id} from {source}",
    }


@tool(description="Attach a piece of evidence to a control.")
async def attach_evidence(
    ctx: ToolContext, *, control: str, evidence_id: str, source: str, summary: str
) -> dict[str, JSONValue]:
    return {
        "attached": _store.attach(
            control,
            {"evidence_id": evidence_id, "source": source, "summary": summary, "by": ctx.principal_id or "system"},
        )
    }


@tool(description="Flag a risk for follow-up. Always paired with a human signoff in regulated verticals.")
async def flag_risk(
    ctx: ToolContext, *, severity: str, description: str, control: str
) -> dict[str, JSONValue]:
    return {
        "risk_id": f"risk_{control}",
        "severity": severity,
        "description": description,
        "control": control,
    }


@tool(description="Sign off on a control after review. Records an audit event.")
async def signoff(ctx: ToolContext, *, control: str, statement: str) -> dict[str, JSONValue]:
    return {
        "signed_off": True,
        "control": control,
        "by": ctx.principal_id or "system",
        "statement": statement,
    }
