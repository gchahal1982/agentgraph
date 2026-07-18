"""FastAPI app: authenticated HTTP layer for the AgentGraph runtime.

Privileged routes fail closed unless ``AG_API_KEY`` is configured. Local-only
experiments can explicitly opt into unauthenticated mode with
``AG_ALLOW_INSECURE_NO_AUTH=1``; production deployments must never set it.
"""
from __future__ import annotations

import hmac
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
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from agentgraph_server.registry import AgentRegistry, RegisteredAgent

_log = structlog.get_logger("agentgraph.server")


class RunBody(BaseModel):
    """Validated request payload for an agent run."""

    agent: str
    input: dict[str, JSONValue] = Field(default_factory=dict)
    principal_id: str | None = None
    principal_roles: list[str] = Field(default_factory=list)


class AppState:
    """Container for app-scoped registry, durable storage, and auth config."""

    def __init__(self, *, storage_url: str | None = None) -> None:
        self.api_key = os.environ.get("AG_API_KEY")
        insecure_requested = os.environ.get("AG_ALLOW_INSECURE_NO_AUTH") == "1"
        self.allow_insecure_no_auth = insecure_requested and not self.api_key
        if not self.api_key and not self.allow_insecure_no_auth:
            raise RuntimeError(
                "AG_API_KEY is required. For local-only development, explicitly set "
                "AG_ALLOW_INSECURE_NO_AUTH=1."
            )
        url = storage_url or default_storage_url()
        self.storage_url = url
        self.registry = AgentRegistry()
        self.checkpoints: CheckpointStore = checkpoint_store_from_url(url)
        self.audit: AuditLog = audit_log_from_url(url)


def _register_verticals(state: AppState) -> None:
    """Build each installed vertical's service and register its graph."""
    specs = [
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
            continue
        try:
            service_cls = getattr(module, service_cls_name)
            service = service_cls.default(storage_url=state.storage_url)
            state.registry.register_sync(
                RegisteredAgent(
                    name=agent_name,
                    description=service_cls.__doc__ or agent_name,
                    vertical=module_name.removeprefix("agentgraph_"),
                    graph=getattr(service, graph_attr),
                )
            )
        except Exception as exc:
            _log.warning(
                "vertical_registration_skipped",
                vertical=module_name,
                error_type=type(exc).__name__,
            )


def create_app(state: AppState | None = None, *, register_verticals: bool = True) -> FastAPI:
    state = state or AppState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if register_verticals:
            _register_verticals(state)
        if state.allow_insecure_no_auth:
            _log.warning(
                "auth_explicitly_disabled",
                message="Unauthenticated local-development mode is active; do not expose this server.",
            )
        try:
            yield
        finally:
            await state.checkpoints.close()
            await state.audit.close()

    app = FastAPI(
        title="AgentGraph",
        version="0.1.0",
        description="Agent runtime for business outcomes.",
        lifespan=lifespan,
    )
    app.state.ag = state

    async def require_api_key(authorization: str | None = Header(default=None)) -> None:
        if state.allow_insecure_no_auth:
            return
        scheme, _, credential = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(credential, state.api_key or ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    auth = [Depends(require_api_key)]

    # --- public health checks (no auth) ---

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        agents = await state.registry.list()
        return {"status": "ready", "agents": str(len(agents))}

    @app.get("/agents", dependencies=auth)
    async def list_agents() -> dict[str, Any]:
        agents = await state.registry.list()
        return {
            "agents": [
                {"name": item.name, "description": item.description, "vertical": item.vertical}
                for item in agents
            ]
        }

    @app.post("/threads", status_code=status.HTTP_201_CREATED, dependencies=auth)
    async def create_thread() -> dict[str, str]:
        return {"thread_id": new_thread_id()}

    @app.get("/threads", dependencies=auth)
    async def list_threads(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, list[dict[str, Any]]]:
        return {"threads": await state.checkpoints.list_threads(limit=limit)}

    @app.post("/threads/{thread_id}/run", dependencies=auth)
    async def run_agent(thread_id: str, body: RunBody) -> dict[str, Any]:
        try:
            agent = await state.registry.get(body.agent)
        except KeyError as exc:
            raise HTTPException(404, f"Agent {body.agent!r} not found") from exc
        principal = None
        if body.principal_id:
            try:
                principal = Principal(
                    id=body.principal_id,
                    roles=[RbacRole(role) for role in body.principal_roles],
                )
            except ValueError as exc:
                raise HTTPException(400, "Invalid principal role") from exc
        runtime = Runtime(
            RuntimeConfig(
                checkpoint_store=state.checkpoints,
                audit_log=state.audit,
                principal=principal,
            )
        )
        try:
            result = await runtime.run(agent.graph, input=body.input, thread_id=thread_id)
        except Exception as exc:
            _log.error(
                "agent_run_failed",
                agent=body.agent,
                thread_id=thread_id,
                error_type=type(exc).__name__,
            )
            raise HTTPException(500, "Agent execution failed") from exc
        if result.error:
            _log.error(
                "agent_run_failed",
                agent=body.agent,
                thread_id=thread_id,
                run_id=result.run.run_id,
            )
            raise HTTPException(500, "Agent execution failed")
        return {
            "run_id": result.run.run_id,
            "thread_id": result.run.thread_id,
            "finished": result.finished,
            "error": None,
            "output": result.values.get("agent_output") or result.values.get("output"),
            "cost_usd": float(result.values.get("total_cost_usd", 0.0) or 0.0),
            "tokens": int(result.values.get("total_tokens", 0) or 0),
        }

    @app.get("/threads/{thread_id}/runs", dependencies=auth)
    async def list_runs(thread_id: str) -> dict[str, list[dict[str, Any]]]:
        checkpoints = await state.checkpoints.list_for_thread(thread_id)
        return {
            "runs": [
                {
                    "id": item.id,
                    "run_id": item.run_id,
                    "thread_id": item.thread_id,
                    "node": item.node,
                    "created_at": item.created_at,
                }
                for item in checkpoints
            ]
        }

    @app.get("/audit", dependencies=auth)
    async def query_audit(
        run_id: str | None = None,
        thread_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, list[dict[str, Any]]]:
        events = await state.audit.query(run_id=run_id, thread_id=thread_id, limit=limit)
        return {"events": [event.model_dump(mode="json") for event in events]}

    return app
