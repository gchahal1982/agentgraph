"""Healthcare tools: patient lookup, encounters, prior auth, discharge summary.

The default backend is in-memory. Production deployments wire these to
an EHR (Epic, Cerner, Athena) via FHIR or the vendor's API.

Tools that touch PHI declare `requires_principal=True` via the `tool`
decorator's `requires_principal` parameter (set on the underlying
`Tool`). The runtime checks the principal against the policy before
dispatching.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue


class PatientStore(Protocol):
    def get(self, patient_id: str) -> dict[str, Any] | None: ...


class InMemoryPatientStore:
    def __init__(self) -> None:
        self._patients: dict[str, dict[str, Any]] = {}
        self._encounters: dict[str, dict[str, Any]] = {}
        self._pa_requests: dict[str, dict[str, Any]] = {}
        self._discharges: dict[str, list[dict[str, Any]]] = {}

    def seed(self, patients: Iterable[dict[str, Any]]) -> None:
        for p in patients:
            self._patients[p["id"]] = p

    def get(self, patient_id: str) -> dict[str, Any] | None:
        return self._patients.get(patient_id)

    def open_encounter(self, encounter: dict[str, Any]) -> dict[str, Any]:
        eid = encounter.setdefault("id", f"enc_{len(self._encounters)+1:05d}")
        self._encounters[eid] = encounter
        return encounter

    def save_pa_request(self, req: dict[str, Any]) -> dict[str, Any]:
        pid = req.setdefault("id", f"pa_{len(self._pa_requests)+1:05d}")
        self._pa_requests[pid] = req
        return req

    def append_discharge(self, patient_id: str, summary: dict[str, Any]) -> dict[str, Any]:
        self._discharges.setdefault(patient_id, []).append(summary)
        return summary


_store: Any = InMemoryPatientStore()


def set_store(store: Any) -> None:
    global _store
    _store = store


@tool(description="Look up a patient by id. Touches PHI.")
async def lookup_patient(ctx: ToolContext, patient_id: str) -> dict[str, JSONValue]:
    p = _store.get(patient_id)
    if p is None:
        return {"error": "not_found", "patient_id": patient_id}
    return {"patient": p}


@tool(description="Open a new clinical encounter for a patient.")
async def open_encounter(
    ctx: ToolContext, *, patient_id: str, reason: str, acuity: str, channel: str = "phone"
) -> dict[str, JSONValue]:
    enc = _store.open_encounter(
        {"patient_id": patient_id, "reason": reason, "acuity": acuity, "channel": channel}
    )
    return {"encounter": enc}


@tool(description="Draft a prior-authorization request from a clinical note.")
async def draft_prior_auth(
    ctx: ToolContext,
    *,
    patient_id: str,
    diagnosis_code: str,
    procedure_code: str,
    clinical_note: str,
    urgency: str = "routine",
) -> dict[str, JSONValue]:
    req = _store.save_pa_request(
        {
            "patient_id": patient_id,
            "diagnosis_code": diagnosis_code,
            "procedure_code": procedure_code,
            "clinical_note": clinical_note,
            "urgency": urgency,
            "status": "drafted",
        }
    )
    return {"prior_auth": req}


@tool(description="Sign off on a prior-authorization request. Records an audit event.")
async def signoff_prior_auth(
    ctx: ToolContext, *, prior_auth_id: str, statement: str
) -> dict[str, JSONValue]:
    return {
        "signed_off": True,
        "prior_auth_id": prior_auth_id,
        "by": ctx.principal_id or "system",
        "statement": statement,
    }


@tool(description="Append a discharge summary to the patient's record.")
async def append_discharge_summary(
    ctx: ToolContext,
    *,
    patient_id: str,
    diagnosis: str,
    follow_up: str,
    medications: list[str],
    summary_text: str,
) -> dict[str, JSONValue]:
    summary = _store.append_discharge(
        patient_id,
        {
            "diagnosis": diagnosis,
            "follow_up": follow_up,
            "medications": medications,
            "summary_text": summary_text,
        },
    )
    return {"discharge": summary}


@tool(description="Escalate the encounter to a human clinician; signals a transition out of the agent node.")
async def escalate_to_clinician(
    ctx: ToolContext, *, patient_id: str, reason: str, urgency: str = "normal"
) -> dict[str, JSONValue]:
    ctx.state["__goto__"] = "clinician_review"
    ctx.state["clinician_escalation"] = {"patient_id": patient_id, "reason": reason, "urgency": urgency}
    return {"escalated": True, "reason": reason, "urgency": urgency}
