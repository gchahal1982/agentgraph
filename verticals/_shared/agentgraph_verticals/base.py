"""Vertical pack scaffolding.

A vertical is a directory that ships:
- A compiled `Graph` (or set of graphs) for a specific business outcome
- The agents, tools, prompts, and policy that the graph uses
- A default `Runner` with sensible audit + checkpoint defaults
- A FastAPI app factory (for embedded deployments)

This module gives verticals a consistent shape without forcing them
through a rigid base class.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from agentgraph_core.audit import AuditLog
from agentgraph_core.rbac import DEFAULT_ROLE_PERMISSIONS, Permission, Principal, RbacRole
from agentgraph_runtime.checkpoint import CheckpointStore
from agentgraph_sdk.runner import Runner


@dataclass(slots=True)
class VerticalMeta:
    """Metadata describing a vertical pack."""

    name: str
    display_name: str
    outcomes: list[str]
    roles: list[RbacRole] = field(default_factory=list)
    description: str = ""
    homepage: str = ""


def default_meta(name: str, display_name: str, outcomes: list[str]) -> VerticalMeta:
    return VerticalMeta(name=name, display_name=display_name, outcomes=outcomes)


class VerticalPack(abc.ABC):
    """Base class for vertical packs.

    Subclasses provide `meta` and `build_runner()`. Optional overrides
    include `build_app()` for a FastAPI service and `seed()` for initial
    reference data.
    """

    meta: VerticalMeta

    @abc.abstractmethod
    def build_runner(
        self,
        *,
        checkpoint_store: CheckpointStore | None = None,
        audit_log: AuditLog | None = None,
        principal: Principal | None = None,
    ) -> Runner:
        ...

    def build_app(self):  # pragma: no cover - optional
        from fastapi import FastAPI

        app = FastAPI(
            title=self.meta.display_name,
            version="0.1.0",
            description=self.meta.description,
        )

        @app.get("/")
        async def root() -> dict[str, Any]:
            return {
                "vertical": self.meta.name,
                "display_name": self.meta.display_name,
                "outcomes": self.meta.outcomes,
            }

        return app

    def roles_for(self, principal_id: str) -> Principal:
        """Default principal used by examples in this vertical."""
        return Principal(id=principal_id, roles=self.meta.roles[:1] if self.meta.roles else [RbacRole.USER])


def with_role(roles: dict[RbacRole, set[Permission]]) -> dict[RbacRole, set[Permission]]:
    """Compose vertical-specific role overrides onto the defaults."""
    out = {r: set(p) for r, p in DEFAULT_ROLE_PERMISSIONS.items()}
    for r, perms in roles.items():
        out.setdefault(r, set()).update(perms)
    return out