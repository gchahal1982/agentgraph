"""Healthcare service."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from agentgraph_core.audit import InMemoryAuditLog
from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_runtime.checkpoint import InMemoryCheckpointStore
from agentgraph_sdk.runner import Runner

from agentgraph_healthcare.graphs import (
    build_healthcare_runner,
    discharge_summary_graph,
    intake_triage_graph,
    prior_auth_graph,
)
from agentgraph_healthcare.tools import InMemoryPatientStore, set_store


@dataclass
class HealthcareService:
    runner: Runner
    intake_graph: Any
    pa_graph: Any
    discharge_graph: Any
    store: InMemoryPatientStore
    intake: Any
    prior_auth: Any
    discharge: Any

    @classmethod
    def default(cls) -> HealthcareService:
        store = InMemoryPatientStore()
        store.seed(_default_seed_patients())
        set_store(store)
        runner = build_healthcare_runner(
            checkpoint_store=InMemoryCheckpointStore(),
            audit_log=InMemoryAuditLog(),
            principal=Principal(id="system", roles=[RbacRole.CLINICIAN]),
        )
        intake_graph, intake_agents = intake_triage_graph()
        pa_graph, pa_agents = prior_auth_graph()
        dc_graph, dc_agents = discharge_summary_graph()
        return cls(
            runner=runner,
            intake_graph=intake_graph,
            pa_graph=pa_graph,
            discharge_graph=dc_graph,
            store=store,
            intake=intake_agents["intake"],
            prior_auth=pa_agents["prior_auth"],
            discharge=dc_agents["discharge"],
        )

    def triage(self, patient_id: str, message: str) -> Any:
        return self.runner.run(self.intake_graph, input={"patient_id": patient_id, "message": message})


def _default_seed_patients() -> list[dict[str, Any]]:
    return [
        {
            "id": "pat_001",
            "name": "Ada Lovelace",
            "dob": "1815-12-10",
            "allergies": ["penicillin"],
        },
        {
            "id": "pat_002",
            "name": "Grace Hopper",
            "dob": "1906-12-09",
            "allergies": [],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-healthcare")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8087")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()
    import uvicorn

    svc = HealthcareService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: HealthcareService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Healthcare", version="0.1.0")

    class IntakeBody(BaseModel):
        patient_id: str
        message: str

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "healthcare", "agents": [svc.intake.config.name, svc.prior_auth.config.name, svc.discharge.config.name]}

    @app.post("/run/intake")
    async def run_intake(body: IntakeBody) -> dict[str, Any]:
        if not body.patient_id or not body.message:
            raise HTTPException(400, "patient_id and message required")
        return svc.triage(patient_id=body.patient_id, message=body.message).to_dict()

    @app.get("/patients")
    async def list_patients() -> dict[str, Any]:
        return {"patients": list(svc.store._patients.values())}

    return app


if __name__ == "__main__":
    main()
