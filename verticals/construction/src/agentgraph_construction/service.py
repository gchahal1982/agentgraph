"""Construction service."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_sdk.runner import Runner

from agentgraph_construction.graphs import (
    build_construction_runner,
    daily_log_graph,
    rfi_drafting_graph,
    submittal_review_graph,
)
from agentgraph_construction.tools import InMemoryProjectStore, set_store


@dataclass
class ConstructionService:
    runner: Runner
    rfi_graph: Any
    submittal_graph: Any
    daily_log_graph_: Any
    store: InMemoryProjectStore
    rfi: Any
    submittal: Any
    daily_log: Any

    @classmethod
    def default(
        cls,
        *,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        storage_url: str | None = None,
    ) -> ConstructionService:
        from agentgraph_llm.base import LLMConfig, default_llm_config

        if llm_provider is not None:
            _llm = LLMConfig(provider=llm_provider, model=llm_model or "default")
        else:
            _llm = default_llm_config(model=llm_model)
        store = InMemoryProjectStore()
        store.seed(_default_seed_projects())
        set_store(store)
        runner = build_construction_runner(
                        principal=Principal(id="system", roles=[RbacRole.CONSTRUCTION_PM]),
            storage_url=storage_url,
        )
        rfi_graph, rfi_agents = rfi_drafting_graph(_llm)
        sub_graph, sub_agents = submittal_review_graph(_llm)
        dl_graph, dl_agents = daily_log_graph(_llm)
        return cls(
            runner=runner,
            rfi_graph=rfi_graph,
            submittal_graph=sub_graph,
            daily_log_graph_=dl_graph,
            store=store,
            rfi=rfi_agents["rfi"],
            submittal=sub_agents["submittal"],
            daily_log=dl_agents["daily_log"],
        )

    def draft_rfi(self, field_notes: str, project_id: str = "PRJ-001") -> Any:
        return self.runner.run(self.rfi_graph, input={"field_notes": field_notes, "project_id": project_id})


def _default_seed_projects() -> list[dict[str, Any]]:
    return [
        {
            "id": "PRJ-001",
            "name": "Analytix HQ Buildout",
            "specs": [
                {"id": "03 30 00", "title": "Cast-in-place Concrete"},
                {"id": "09 65 19", "title": "Resilient Floor Tile"},
            ],
        },
        {
            "id": "PRJ-002",
            "name": "BuildWell Yard Expansion",
            "specs": [
                {"id": "31 20 00", "title": "Earth Moving"},
                {"id": "32 12 16", "title": "Asphalt Paving"},
            ],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-construction")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8086")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()
    import uvicorn

    svc = ConstructionService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: ConstructionService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Construction", version="0.1.0")

    class RfiBody(BaseModel):
        field_notes: str
        project_id: str = "PRJ-001"

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "construction", "agents": [svc.rfi.config.name, svc.submittal.config.name, svc.daily_log.config.name]}

    @app.post("/run/rfi")
    async def run_rfi(body: RfiBody) -> dict[str, Any]:
        return svc.draft_rfi(field_notes=body.field_notes, project_id=body.project_id).to_dict()

    @app.get("/projects")
    async def list_projects() -> dict[str, Any]:
        return {"projects": [svc.store.get(p) for p in svc.store._projects]}

    return app


if __name__ == "__main__":
    main()
