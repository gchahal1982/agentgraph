"""Construction tools: RFIs, submittals, daily log, project lookup."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue


class ProjectStore(Protocol):
    def get(self, project_id: str) -> dict[str, Any] | None: ...

    def save_rfi(self, rfi: dict[str, Any]) -> dict[str, Any]: ...

    def save_submittal(self, submittal: dict[str, Any]) -> dict[str, Any]: ...

    def append_log(self, project_id: str, entry: dict[str, Any]) -> dict[str, Any]: ...


class InMemoryProjectStore:
    def __init__(self) -> None:
        self._projects: dict[str, dict[str, Any]] = {}
        self._rfis: dict[str, dict[str, Any]] = {}
        self._submittals: dict[str, dict[str, Any]] = {}
        self._logs: dict[str, list[dict[str, Any]]] = {}

    def seed(self, projects: Iterable[dict[str, Any]]) -> None:
        for p in projects:
            self._projects[p["id"]] = p

    def get(self, project_id: str) -> dict[str, Any] | None:
        return self._projects.get(project_id)

    def save_rfi(self, rfi: dict[str, Any]) -> dict[str, Any]:
        rid = rfi.setdefault("id", f"rfi_{len(self._rfis) + 1:04d}")
        self._rfis[rid] = rfi
        return rfi

    def save_submittal(self, submittal: dict[str, Any]) -> dict[str, Any]:
        sid = submittal.setdefault("id", f"sub_{len(self._submittals) + 1:04d}")
        self._submittals[sid] = submittal
        return submittal

    def append_log(self, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        self._logs.setdefault(project_id, []).append(entry)
        return entry


_store: ProjectStore = InMemoryProjectStore()


def set_store(s: ProjectStore) -> None:
    global _store
    _store = s


@tool(description="Create an RFI (Request for Information) from structured fields.")
async def create_rfi(
    ctx: ToolContext,
    *,
    project_id: str,
    subject: str,
    question: str,
    spec_reference: str,
    requested_by: str,
    due_date: str,
) -> dict[str, JSONValue]:
    if hasattr(_store, "save_rfi"):
        rfi = _store.save_rfi(
            {
                "project_id": project_id,
                "subject": subject,
                "question": question,
                "spec_reference": spec_reference,
                "requested_by": requested_by,
                "due_date": due_date,
            }
        )
        return {"rfi": rfi}
    return {"error": "rfi_storage_unavailable"}


@tool(description="List the spec sections referenced by a project.")
async def list_specs(ctx: ToolContext, project_id: str) -> dict[str, JSONValue]:
    p = _store.get(project_id) if hasattr(_store, "get") else None
    return {"specs": (p or {}).get("specs", [])}


@tool(description="Review a submittal against a spec and record the verdict.")
async def review_submittal(
    ctx: ToolContext,
    *,
    submittal_id: str,
    spec_reference: str,
    verdict: str,
    rationale: str,
) -> dict[str, JSONValue]:
    if hasattr(_store, "save_submittal"):
        sub = _store.save_submittal(
            {
                "submittal_id": submittal_id,
                "spec_reference": spec_reference,
                "verdict": verdict,
                "rationale": rationale,
            }
        )
        return {"submittal": sub}
    return {"error": "submittal_storage_unavailable"}


@tool(description="Append an entry to the project's daily log.")
async def append_daily_log(
    ctx: ToolContext,
    *,
    project_id: str,
    entry: str,
    weather: str = "",
    crew_size: int = 0,
) -> dict[str, JSONValue]:
    if hasattr(_store, "append_log"):
        log = _store.append_log(
            project_id,
            {
                "entry": entry,
                "weather": weather,
                "crew_size": crew_size,
                "by": ctx.principal_id or "system",
            },
        )
        return {"log": log}
    return {"error": "log_unavailable"}


@tool(description="Look up a project by id. Returns project metadata + spec list.")
async def lookup_project(ctx: ToolContext, project_id: str) -> dict[str, JSONValue]:
    p = _store.get(project_id)
    return {"project": p} if p else {"error": "not_found", "project_id": project_id}


@tool(
    description="Escalate an issue to the project manager; signals a transition out of the agent node."
)
async def escalate_to_pm(
    ctx: ToolContext, *, project_id: str, reason: str, priority: str = "normal"
) -> dict[str, JSONValue]:
    ctx.state["__goto__"] = "pm_review"
    ctx.state["pm_escalation"] = {"project_id": project_id, "reason": reason, "priority": priority}
    return {"escalated": True, "reason": reason}
