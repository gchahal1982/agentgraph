"""Sales-ops service: pre-wires the graphs, agents, and CRM into a FastAPI app.

Run with `ag-sales-ops` (see `service:main`) or import and embed in your
own application.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Any

from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_sdk.runner import Runner

from agentgraph_sales_ops.graphs import (
    build_sales_ops_runner,
    lead_qualification_graph,
    pipeline_summary_graph,
)
from agentgraph_sales_ops.tools import InMemoryCRM, set_crm


@dataclass
class SalesOpsService:
    """A pre-wired service with CRM, runner, and graphs.

    Example::

        svc = SalesOpsService.default()
        result = svc.runner.run(svc.lead_graph, input={"contact_email": "ada@analytix.com"})
    """

    runner: Runner
    lead_graph: Any
    pipeline_graph: Any
    crm: InMemoryCRM
    qualifier: Any = field(default=None, repr=False)
    outreach: Any = field(default=None, repr=False)
    reviewer: Any = field(default=None, repr=False)

    @classmethod
    def default(
        cls,
        *,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        storage_url: str | None = None,
    ) -> SalesOpsService:
        from agentgraph_llm.base import LLMConfig, default_llm_config

        if llm_provider is not None:
            llm = LLMConfig(provider=llm_provider, model=llm_model or "default")
        else:
            llm = default_llm_config(model=llm_model)
        crm = InMemoryCRM()
        crm.seed(_default_seed_accounts())
        set_crm(crm)
        runner = build_sales_ops_runner(
            principal=Principal(id="system", roles=[RbacRole.SALES_REP]),
            storage_url=storage_url,
        )
        lead_graph, lead_agents = lead_qualification_graph(llm)
        pipe_graph, pipe_agents = pipeline_summary_graph(llm)
        return cls(
            runner=runner,
            lead_graph=lead_graph,
            pipeline_graph=pipe_graph,
            crm=crm,
            qualifier=lead_agents["qualifier"],
            outreach=lead_agents["outreach"],
            reviewer=pipe_agents["reviewer"],
        )

    def run_lead(self, contact_email: str, **kwargs: Any) -> Any:
        return self.runner.run(self.lead_graph, input={"contact_email": contact_email, **kwargs})

    def run_pipeline_review(self, account_id: str) -> Any:
        return self.runner.run(self.pipeline_graph, input={"account_id": account_id})


def _default_seed_accounts() -> list[dict[str, Any]]:
    return [
        {
            "id": "acct_analytix",
            "domain": "analytix.com",
            "name": "Analytix",
            "size": 250,
            "industry": "saas",
            "contacts": [
                {"name": "Ada Lovelace", "email": "ada@analytix.com", "title": "VP Eng"},
                {"name": "Grace Hopper", "email": "grace@analytix.com", "title": "CTO"},
            ],
        },
        {
            "id": "acct_buildwell",
            "domain": "buildwell.co",
            "name": "BuildWell Construction",
            "size": 80,
            "industry": "construction",
            "contacts": [
                {"name": "Henry Ford", "email": "henry@buildwell.co", "title": "Operations Lead"},
            ],
        },
        {
            "id": "acct_clariwell",
            "domain": "clariwell.io",
            "name": "Clariwell",
            "size": 35,
            "industry": "healthtech",
            "contacts": [
                {"name": "Marie Curie", "email": "marie@clariwell.io", "title": "Founder"},
            ],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-sales-ops")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8081")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()

    import uvicorn

    svc = SalesOpsService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: SalesOpsService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Sales Ops", version="0.1.0")

    class RunBody(BaseModel):
        contact_email: str | None = None
        account_id: str | None = None

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "sales-ops", "agents": [svc.qualifier.config.name, svc.outreach.config.name, svc.reviewer.config.name]}

    @app.post("/run/lead")
    async def run_lead(body: RunBody) -> dict[str, Any]:
        if not (body.contact_email or body.account_id):
            raise HTTPException(400, "contact_email or account_id required")
        result = svc.run_lead(contact_email=body.contact_email or "", account_id=body.account_id or "")
        return result.to_dict()

    @app.post("/run/pipeline")
    async def run_pipeline(body: RunBody) -> dict[str, Any]:
        if not body.account_id:
            raise HTTPException(400, "account_id required")
        result = svc.run_pipeline_review(body.account_id)
        return result.to_dict()

    @app.get("/accounts")
    async def accounts() -> dict[str, Any]:
        return {"accounts": svc.crm.list_accounts()}

    return app


if __name__ == "__main__":
    main()
