"""Insurance service."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from agentgraph_core.audit import InMemoryAuditLog
from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_runtime.checkpoint import InMemoryCheckpointStore
from agentgraph_sdk.runner import Runner

from agentgraph_insurance.graphs import (
    build_insurance_runner,
    claims_triage_graph,
    fnol_intake_graph,
    underwriting_copilot_graph,
)
from agentgraph_insurance.tools import (
    InMemoryClaimStore,
    InMemoryPolicyStore,
    set_claim_store,
    set_policy_store,
)


@dataclass
class InsuranceService:
    runner: Runner
    fnol_graph: Any
    underwriting_graph: Any
    claims_graph: Any
    claims: InMemoryClaimStore
    policies: InMemoryPolicyStore
    fnol: Any
    underwriter: Any
    triage: Any

    @classmethod
    def default(cls) -> InsuranceService:
        policies = InMemoryPolicyStore()
        policies.seed(_default_seed_policies())
        set_policy_store(policies)
        claims = InMemoryClaimStore()
        set_claim_store(claims)
        runner = build_insurance_runner(
            checkpoint_store=InMemoryCheckpointStore(),
            audit_log=InMemoryAuditLog(),
            principal=Principal(id="system", roles=[RbacRole.INSURANCE_UNDERWRITER]),
        )
        fnol_graph, fnol_agents = fnol_intake_graph()
        uw_graph, uw_agents = underwriting_copilot_graph()
        triage_graph, triage_agents = claims_triage_graph()
        return cls(
            runner=runner,
            fnol_graph=fnol_graph,
            underwriting_graph=uw_graph,
            claims_graph=triage_graph,
            claims=claims,
            policies=policies,
            fnol=fnol_agents["fnol"],
            underwriter=uw_agents["underwriter"],
            triage=triage_agents["triage"],
        )

    def capture_fnol(self, description: str, policy_id: str = "POL-1001") -> Any:
        return self.runner.run(self.fnol_graph, input={"description": description, "policy_id": policy_id})

    def underwrite(self, applicant: dict[str, Any]) -> Any:
        return self.runner.run(self.underwriting_graph, input=applicant)

    def triage_claims(self) -> Any:
        return self.runner.run(self.claims_graph, input={"open_claims": self.claims.list_open()})


def _default_seed_policies() -> list[dict[str, Any]]:
    return [
        {"id": "POL-1001", "holder": "Ada Lovelace", "type": "auto", "coverage_usd": 50_000},
        {"id": "POL-1002", "holder": "Grace Hopper", "type": "property", "coverage_usd": 500_000},
        {"id": "POL-1003", "holder": "Linus Torvalds", "type": "liability", "coverage_usd": 1_000_000},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-insurance")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8085")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()
    import uvicorn

    svc = InsuranceService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: InsuranceService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Insurance", version="0.1.0")

    class FnolBody(BaseModel):
        description: str
        policy_id: str = "POL-1001"

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "insurance", "agents": [svc.fnol.config.name, svc.underwriter.config.name, svc.triage.config.name]}

    @app.post("/run/fnol")
    async def run_fnol(body: FnolBody) -> dict[str, Any]:
        return svc.capture_fnol(description=body.description, policy_id=body.policy_id).to_dict()

    @app.get("/claims")
    async def list_claims() -> dict[str, Any]:
        return {"claims": svc.claims.list_open()}

    return app


if __name__ == "__main__":
    main()
