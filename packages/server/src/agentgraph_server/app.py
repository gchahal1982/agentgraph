"""FastAPI app: production HTTP layer for the AgentGraph runtime.

The server registers every installed vertical's agents at startup, persists
runs and the audit log to durable storage (`AG_STORAGE_URL`), and protects
all privileged routes with bearer-token auth (`AG_API_KEY`).

Environment:
  AG_API_KEY      Required for auth. If unset, the server starts in
                  open mode and logs a prominent warning (development only).
  AG_STORAGE_URL  Storage backend (default: SQLite under the data dir).
  AG_LLM_PROVIDER / AG_LLM_MODEL and the provider's key env var
                  (e.g. OPENAI_API_KEY) select the model used by agents.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import structlog
from agentgraph_core.audit import AuditLog
from agentgraph_core.ids import new_thread_id
from agentgraph_core.rbac import Principal, RbacRole
from agentgraph_core.storage import audit_log_from_url, default_storage_url
from agentgraph_core.types import JSONValue
from agentgraph_runtime.checkpoint import CheckpointStore, checkpoint_store_from_url
from agentgraph_runtime.runtime import Runtime, RuntimeConfig
from agentgraph_runtime.state import GraphState
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from agentgraph_server.registry import AgentRegistry, RegisteredAgent

_log = structlog.get_logger("agentgraph.server")


class AppState:
    """Container for app-scoped singletons (registry + durable storage)."""

    def __init__(self, *, storage_url: str | None = None) -> None:
        url = storage_url or default_storage_url()
        self.storage_url = url
        self.registry = AgentRegistry()
        self.checkpoints: CheckpointStore = checkpoint_store_from_url(url)
        self.audit: AuditLog = audit_log_from_url(url)
        self.api_key = os.environ.get("AG_API_KEY")


# --- vertical registration ---

# (module path, factory attr, mapping of agent name -> (graph attr, role))
_VERTICALS: list[str] = [
    "agentgraph_sales_ops",
    "agentgraph_support_ops",
    "agentgraph_compliance",
    "agentgraph_recruiting",
    "agentgraph_insurance",
    "agentgraph_construction",
    "agentgraph_healthcare",
]


def _register_verticals(state: AppState) -> None:
    """Build each installed vertical's service and register its graphs.

    A vertical that cannot be configured (e.g. its LLM provider key is
    missing) is skipped with a warning so the server still starts with the
    verticals that *are* configured.
    """
    specs: list[tuple[str, str, str, str]] = [
        # (module, Service class, agent name, graph attribute)
        ("agentgraph_sales_ops", "SalesOpsService", "qualify_lead", "lead_graph"),
        ("agentgraph_support_ops", "SupportOpsService", "triage_ticket", "triage_graph"),
        ("agentgraph_compliance", "ComplianceService", "policy_review", "review_graph"),
        ("agentgraph_recruiting", "RecruitingService", "source_candidates", "sourcing_graph"),
        ("agentgraph_insurance", "InsuranceService", "fnol_intake", "fnol_graph"),
        ("agentgraph_construction", "ConstructionService", "draft_rfi", "rfi_graph"),
        ("agentgraph_healthcare", "HealthcareService", "intake_triage", "intake_graph"),
    ]
    import importlib

    for module_name, service_cls_name, agent_name, graph_attr in specs:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue  # vertical not installed
        try:
            service_cls = getattr(module, service_cls_name)
            service = service_cls.default(storage_url=state.storage_url)
            graph = getattr(service, graph_attr)
            state.registry.register_sync(
                RegisteredAgent(
                    name=agent_name,
                    description=service_cls.__doc__ or agent_name,
                    vertical=module_name.replace("agentgraph_", ""),
                    graph=graph,
                )
            )
        except Exception as e:  # noqa: BLE001
            _log.warning(
                "vertical_registration_skipped",
                vertical=module_name,
                error=f"{type(e).__name__}: {e}",
            )
                )
            )
        except Exception as e:
            _log.warning(
                "vertical_registration_skipped",
                vertical=module_name,
                error=f"{type(e).__name__}: {e}",
            )


def create_app(state: AppState | None = None, *, register_verticals: bool = True) -> FastAPI:
    state = state or AppState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if register_verticals:
            _register_verticals(state)
        if not state.api_key:
            _log.warning(
                "auth_disabled",
                message="AG_API_KEY is not set; the API is unauthenticated. "
                "Set AG_API_KEY before exposing this server.",
            )
        yield

    app = FastAPI(
        title="AgentGraph",
        version="0.1.0",
        description="Agent runtime for business outcomes.",
        lifespan=lifespan,
    )
    app.state.ag = state

    # --- auth dependency ---

    async def require_api_key(authorization: str | None = Header(default=None)) -> None:
        if not state.api_key:
            return  # open mode (a startup warning was logged)
        expected = f"Bearer {state.api_key}"
        if authorization != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    auth = [Depends(require_api_key)]

    # --- models ---

    class RunBody(BaseModel):
        agent: str
        input: dict[str, JSONValue] = Field(default_factory=dict)
        principal_id: str | None = None
        principal_roles: list[str] = Field(default_factory=list)

    # --- public health checks (no auth) ---

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        agents = await state.registry.list()
        return {"status": "ready", "agents": str(len(agents))}

    # --- agents ---

    @app.get("/agents", dependencies=auth)
    async def list_agents() -> dict[str, Any]:
        agents = await state.registry.list()
        return {
            "agents": [
                {"name": a.name, "description": a.description, "vertical": a.vertical}
                for a in agents
            ]
        }

    # --- threads ---

    @app.post("/threads", status_code=status.HTTP_201_CREATED, dependencies=auth)
    async def create_thread() -> dict[str, str]:
        return {"thread_id": new_thread_id()}

    @app.post("/threads/{thread_id}/run", dependencies=auth)
    async def run_agent(thread_id: str, body: RunBody) -> dict[str, Any]:
        try:
            agent = await state.registry.get(body.agent)
        except KeyError as e:
            raise HTTPException(404, f"Agent {body.agent!r} not found") from e
        principal = None
        if body.principal_id:
            try:
                principal = Principal(
                    id=body.principal_id,
                    roles=[RbacRole(r) for r in body.principal_roles],
                )
            except ValueError as e:
                raise HTTPException(400, f"Invalid role: {e}") from e
        rt = Runtime(
            RuntimeConfig(
                checkpoint_store=state.checkpoints,
                audit_log=state.audit,
                principal=principal,
            )
        )
        try:
            result: GraphState = await rt.run(
                agent.graph, input=body.input, thread_id=thread_id, principal=principal
            )
        except Exception as e:
            raise HTTPException(500, f"{type(e).__name__}: {e}") from e
        return {
            "run_id": result.run.run_id,
            "thread_id": result.run.thread_id,
            "finished": result.finished,
            "error": result.error,
            "output": result.values.get("agent_output") or result.values.get("output"),
            "cost_usd": float(result.values.get("total_cost_usd", 0.0) or 0.0),
            "tokens": int(result.values.get("total_tokens", 0) or 0),
        }

    @app.get("/threads/{thread_id}/runs", dependencies=auth)
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

    @app.get("/audit", dependencies=auth)
    async def query_audit(
        run_id: str | None = None, thread_id: str | None = None, limit: int = 100
    ) -> dict[str, list[dict[str, Any]]]:
        events = await state.audit.query(run_id=run_id, thread_id=thread_id, limit=limit)
        return {"events": [e.model_dump(mode="json") for e in events]}

    return app
