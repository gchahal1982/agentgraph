"""Compliance service: pre-wires evidence store, runner, and graphs."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_sdk.runner import Runner

from agentgraph_compliance.graphs import (
    audit_report_graph,
    build_compliance_runner,
    policy_review_graph,
)
from agentgraph_compliance.tools import InMemoryEvidenceStore, set_store


@dataclass
class ComplianceService:
    runner: Runner
    review_graph: Any
    audit_graph: Any
    store: InMemoryEvidenceStore
    reviewer: Any
    auditor: Any

    @classmethod
    def default(cls) -> ComplianceService:
        store = InMemoryEvidenceStore()
        store.seed("soc2", _default_seed_soc2())
        set_store(store)
        runner = build_compliance_runner(
            checkpoint_store=InMemoryCheckpointStore(),
            audit_log=InMemoryAuditLog(),
            principal=Principal(id="system", roles=[RbacRole.COMPLIANCE_OFFICER]),
        )
        review_graph, review_agents = policy_review_graph()
        audit_graph, audit_agents = audit_report_graph()
        return cls(
            runner=runner,
            review_graph=review_graph,
            audit_graph=audit_graph,
            store=store,
            reviewer=review_agents["reviewer"],
            auditor=audit_agents["auditor"],
        )

    def review(self, control: str, framework: str = "soc2") -> Any:
        return self.runner.run(self.review_graph, input={"control": control, "framework": framework})

    def audit(self, framework: str = "soc2") -> Any:
        return self.runner.run(self.audit_graph, input={"framework": framework})


def _default_seed_soc2() -> list[dict[str, Any]]:
    return [
        {
            "id": "CC1.1",
            "title": "Code of conduct",
            "evidence": [
                {"evidence_id": "doc-001", "source": "hr", "summary": "Code of conduct signed by all employees"},
            ],
        },
        {
            "id": "CC6.1",
            "title": "Logical access controls",
            "evidence": [
                {"evidence_id": "aws-iam-001", "source": "aws", "summary": "MFA enforced for all IAM users"},
            ],
        },
        {
            "id": "CC7.2",
            "title": "Monitoring",
            "evidence": [],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-compliance")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8083")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()
    import uvicorn

    svc = ComplianceService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: ComplianceService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Compliance", version="0.1.0")

    class ReviewBody(BaseModel):
        control: str
        framework: str = "soc2"

    class AuditBody(BaseModel):
        framework: str = "soc2"

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "compliance", "agents": [svc.reviewer.config.name, svc.auditor.config.name]}

    @app.post("/run/review")
    async def run_review(body: ReviewBody) -> dict[str, Any]:
        if not body.control:
            raise HTTPException(400, "control required")
        return svc.review(control=body.control, framework=body.framework).to_dict()

    @app.post("/run/audit")
    async def run_audit(body: AuditBody) -> dict[str, Any]:
        return svc.audit(framework=body.framework).to_dict()

    @app.get("/controls")
    async def list_controls() -> dict[str, Any]:
        return {"controls": list(svc.store._store.keys())}

    return app


if __name__ == "__main__":
    main()
