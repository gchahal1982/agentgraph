"""Recruiting role overrides."""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

RECRUITING_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.RECRUITER: {
            Permission.WRITE_DATA,
        },
    }
)
