"""Recruiting service."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_sdk.runner import Runner

from agentgraph_recruiting.graphs import (
    build_recruiting_runner,
    candidate_screening_graph,
    candidate_sourcing_graph,
)
from agentgraph_recruiting.tools import InMemoryCandidatePool, set_pool


@dataclass
class RecruitingService:
    runner: Runner
    sourcing_graph: Any
    screening_graph: Any
    pool: InMemoryCandidatePool
    sourcer: Any
    screener: Any

    @classmethod
    def default(
        cls,
        *,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        storage_url: str | None = None,
    ) -> RecruitingService:
        from agentgraph_llm.base import LLMConfig, default_llm_config

        if llm_provider is not None:
            _llm = LLMConfig(provider=llm_provider, model=llm_model or "default")
        else:
            _llm = default_llm_config(model=llm_model)
        pool = InMemoryCandidatePool()
        pool.seed(_default_seed_candidates())
        set_pool(pool)
        runner = build_recruiting_runner(
                        principal=Principal(id="system", roles=[RbacRole.RECRUITER]),
            storage_url=storage_url,
        )
        sourcing_graph, sourcing_agents = candidate_sourcing_graph(_llm)
        screening_graph, screening_agents = candidate_screening_graph(_llm)
        return cls(
            runner=runner,
            sourcing_graph=sourcing_graph,
            screening_graph=screening_graph,
            pool=pool,
            sourcer=sourcing_agents["sourcer"],
            screener=screening_agents["screener"],
        )

    def source_candidates(self, role_title: str, required_skills: list[str], years_experience: int = 3) -> Any:
        return self.runner.run(
            self.sourcing_graph,
            input={"role_title": role_title, "required_skills": required_skills, "years_experience": years_experience},
        )

    def screen_candidate(self, candidate_id: str, role_title: str, required_skills: list[str], years_experience: int = 3) -> Any:
        return self.runner.run(
            self.screening_graph,
            input={
                "candidate_id": candidate_id,
                "role_title": role_title,
                "required_skills": required_skills,
                "years_experience": years_experience,
            },
        )


def _default_seed_candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "cand_001",
            "name": "Ada Lovelace",
            "title": "Senior Backend Engineer",
            "skills": ["python", "distributed systems", "kubernetes", "postgres"],
            "years_experience": 8,
            "summary": "Built distributed systems at scale for analytics platforms.",
        },
        {
            "id": "cand_002",
            "name": "Grace Hopper",
            "title": "Staff Engineer",
            "skills": ["python", "rust", "compilers", "postgres"],
            "years_experience": 12,
            "summary": "Compiler and database engineer; ex-Meta staff.",
        },
        {
            "id": "cand_003",
            "name": "Linus Torvalds",
            "title": "Kernel Engineer",
            "skills": ["c", "linux", "git"],
            "years_experience": 25,
            "summary": "Kernel and tooling.",
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-recruiting")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8084")))
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()
    import uvicorn

    svc = RecruitingService.default()
    app = _build_app(svc)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


def _build_app(svc: RecruitingService):  # pragma: no cover - runtime entrypoint
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="AgentGraph Recruiting", version="0.1.0")

    class SourceBody(BaseModel):
        role_title: str
        required_skills: list[str]
        years_experience: int = 3

    class ScreenBody(BaseModel):
        candidate_id: str
        role_title: str
        required_skills: list[str]
        years_experience: int = 3

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {"vertical": "recruiting", "agents": [svc.sourcer.config.name, svc.screener.config.name]}

    @app.post("/run/source")
    async def run_source(body: SourceBody) -> dict[str, Any]:
        return svc.source_candidates(
            role_title=body.role_title,
            required_skills=body.required_skills,
            years_experience=body.years_experience,
        ).to_dict()

    @app.post("/run/screen")
    async def run_screen(body: ScreenBody) -> dict[str, Any]:
        if not body.candidate_id:
            raise HTTPException(400, "candidate_id required")
        return svc.screen_candidate(
            candidate_id=body.candidate_id,
            role_title=body.role_title,
            required_skills=body.required_skills,
            years_experience=body.years_experience,
        ).to_dict()

    @app.get("/candidates")
    async def list_candidates() -> dict[str, Any]:
        return {"candidates": list(svc.pool._by_id.values())}

    return app


if __name__ == "__main__":
    main()
