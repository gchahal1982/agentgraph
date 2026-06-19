"""Support-ops service: pre-wires KB, ticketing, and graphs into a FastAPI app."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_sdk.runner import Runner

from agentgraph_support_ops.graphs import (
    build_support_ops_runner,
    csat_loop_graph,
    ticket_triage_graph,
)
from agentgraph_support_ops.tools import InMemoryKB, InMemoryTicketing, set_kb, set_ticketing


@dataclass
class SupportOpsService:
    runner: Runner
    triage_graph: Any
    csat_graph: Any
    kb: InMemoryKB
    ticketing: InMemoryTicketing
    triage: Any
    csat: Any

    @classmethod
    def default(cls) -> SupportOpsService:
        kb = InMemoryKB()
        kb.seed(_default_seed_kb())
        set_kb(kb)
        ticketing = InMemoryTicketing()
        set_ticketing(ticketing)
        runner = build_support_ops_runner(
            checkpoint_store=InMemoryCheckpointStore(),
            audit_log=InMemoryAuditLog(),
            principal=Principal(id="system", roles=[RbacRole.SUPPORT_AGENT]),
        )
        triage_graph, triage_agents = ticket_triage_graph()
        csat_graph, csat_agents = csat_loop_graph()
        return cls(
            runner=runner,
            triage_graph=triage_graph,
            csat_graph=csat_graph,
            kb=kb,
            ticketing=ticketing,
            triage=triage_agents["triage"],
            csat=csat_agents["csat"],
        )

    def triage_ticket(self, message: str, requester_email: str = "user@example.com") -> Any:
        return self.runner.run(self.triage_graph, input={"message": message, "requester_email": requester_email})


def _default_seed_kb() -> list[dict[str, Any]]:
    return [
        {
            "title": "How to reset your password",
            "body": "Visit /reset-password, enter your email, and follow the link we send.",
            "tags": ["account", "password"],
        },
        {
            "title": "Updating billing information",
            "body": "Go to Settings -> Billing -> Update card. Changes take effect on your next invoice.",
            "tags": ["billing"],
        },
        {
            "title": "Why is my dashboard slow?",
            "body": "If your dashboard is loading slowly, try clearing your browser cache. If the issue persists, contact support with a screenshot.",
            "tags": ["performance"],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-support-ops")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8082")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()
    import uvicorn

    svc = SupportOpsService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: SupportOpsService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Support Ops", version="0.1.0")

    class TriageBody(BaseModel):
        message: str
        requester_email: str = "user@example.com"

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "support-ops", "agents": [svc.triage.config.name, svc.csat.config.name]}

    @app.post("/run/triage")
    async def run_triage(body: TriageBody) -> dict[str, Any]:
        result = svc.triage_ticket(message=body.message, requester_email=body.requester_email)
        return result.to_dict()

    @app.get("/kb")
    async def list_kb() -> dict[str, Any]:
        return {"articles": [a for a in svc.kb._articles]}

    @app.get("/tickets")
    async def list_tickets() -> dict[str, Any]:
        return {"tickets": list(svc.ticketing._tickets.values())}

    return app


if __name__ == "__main__":
    main()
