"""Construction role overrides."""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

CONSTRUCTION_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.CONSTRUCTION_PM: {
            Permission.READ_PII,
            Permission.INVOKE_BILLING,
        },
    }
)
