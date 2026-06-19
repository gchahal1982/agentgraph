"""Compliance role overrides.

Compliance officers need admin permissions (read everything, attach
evidence, sign off) but not network access (they don't send messages).
"""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

COMPLIANCE_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.COMPLIANCE_OFFICER: {
            Permission.WRITE_DATA,
            Permission.INVOKE_BILLING,  # audit-ready cost breakdowns
        },
    }
)
