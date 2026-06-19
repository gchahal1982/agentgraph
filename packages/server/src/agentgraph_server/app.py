"""FastAPI app: HTTP layer for the AgentGraph runtime."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from agentgraph_core.audit import InMemoryAuditLog
from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_core.types import JSONValue
from agentgraph_runtime.checkpoint import InMemoryCheckpointStore
from agentgraph_runtime.runtime import Runtime, RuntimeConfig
from agentgraph_runtime.state import GraphState
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from agentgraph_server.registry import AgentRegistry, RegisteredAgent


class AppState:
    """Container for app-scoped singletons."""

    def __init__(self) -> None:
        self.registry = AgentRegistry()
        self.checkpoints = InMemoryCheckpointStore()
        self.audit = InMemoryAuditLog()
        self.runtime = Runtime(
            RuntimeConfig(
                checkpoint_store=self.checkpoints,
                audit_log=self.audit,
            )
        )


def create_app(state: AppState | None = None) -> FastAPI:
    state = state or AppState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Hook for startup: load vertical agents, etc.
        yield

    app = FastAPI(
        title="AgentGraph",
        version="0.1.0",
        description="Agent runtime for business outcomes.",
        lifespan=lifespan,
    )
    app.state.ag = state

    # --- request / response models ---

    class RegisterAgentBody(BaseModel):
        name: str
        description: str = ""
        vertical: str = "custom"
        # We accept a serialized graph spec; full server-side compile of
        # arbitrary Python is out of scope. Production deployments should
        # ship pre-compiled agents and register them at startup.
        graph: dict[str, Any] | None = None
        metadata: dict[str, JSONValue] = Field(default_factory=dict)

    class RunBody(BaseModel):
        agent: str
        input: dict[str, JSONValue] = Field(default_factory=dict)
        principal_id: str | None = None
        principal_roles: list[str] = Field(default_factory=list)

    class ThreadBody(BaseModel):
        principal_id: str | None = None

    # --- endpoints ---

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/agents")
    async def list_agents() -> dict[str, Any]:
        agents = await state.registry.list()
        return {
            "agents": [
                {
                    "name": a.name,
                    "description": a.description,
                    "vertical": a.vertical,
                    "metadata": a.metadata,
                }
                for a in agents
            ]
        }

    @app.post("/agents", status_code=status.HTTP_201_CREATED)
    async def register_agent(body: RegisterAgentBody) -> dict[str, str]:
        if body.graph is None:
            raise HTTPException(400, "Register a pre-compiled agent via state.registry.register")
        # Server-side compile of a user-supplied graph spec is not enabled
        # in this build. Vertical packs register their agents at startup.
        await state.registry.register(
            RegisteredAgent(
                name=body.name,
                description=body.description,
                vertical=body.vertical,
                graph=None,  # type: ignore[arg-type]
                metadata=body.metadata,
            )
        )
        return {"name": body.name}

    @app.post("/threads", status_code=status.HTTP_201_CREATED)
    async def create_thread(body: ThreadBody | None = None) -> dict[str, str]:
        from agentgraph_core.ids import new_thread_id

        return {"thread_id": new_thread_id()}

    @app.get("/threads")
    async def list_threads() -> dict[str, list[str]]:
        # We don't persist threads separately; clients should track them.
        return {"threads": []}

    @app.post("/threads/{thread_id}/run")
    async def run_agent(thread_id: str, body: RunBody) -> dict[str, Any]:
        agent = await state.registry.get(body.agent)
        if agent.graph is None:
            raise HTTPException(400, f"Agent {body.agent!r} has no compiled graph")
        principal = None
        if body.principal_id:
            principal = Principal(
                id=body.principal_id,
                roles=[RbacRole(r) for r in body.principal_roles],
            )
        # Use a runtime that has a fresh state for this run but shares
        # the audit log and checkpoint store.
        rt = Runtime(
            RuntimeConfig(
                checkpoint_store=state.checkpoints,
                audit_log=state.audit,
                principal=principal,
            )
        )
        state_obj: GraphState = await rt.run(
            agent.graph,
            input=body.input,
            thread_id=thread_id,
            principal=principal,
        )
        return {
            "run_id": state_obj.run.run_id,
            "thread_id": state_obj.run.thread_id,
            "finished": state_obj.finished,
            "error": state_obj.error,
            "output": state_obj.values.get("agent_output") or state_obj.values.get("output"),
            "cost_usd": float(state_obj.values.get("total_cost_usd", 0.0) or 0.0),
            "tokens": int(state_obj.values.get("total_tokens", 0) or 0),
            "values": state_obj.values,
        }

    @app.get("/threads/{thread_id}/runs")
    async def list_runs(thread_id: str) -> dict[str, list[dict[str, Any]]]:
        cps = await state.checkpoints.list_for_thread(thread_id)
        return {
            "runs": [
                {
                    "id": c.id,
                    "run_id": c.run_id,
                    "thread_id": c.thread_id,
                    "node": c.node,
                    "created_at": c.created_at,
                }
                for c in cps
            ]
        }

    @app.get("/audit")
    async def query_audit(run_id: str | None = None, thread_id: str | None = None, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        events = await state.audit.query(run_id=run_id, thread_id=thread_id, limit=limit)
        return {"events": [e.model_dump(mode="json") for e in events]}

    return app
