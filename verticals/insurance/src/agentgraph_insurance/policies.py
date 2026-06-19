"""Insurance role overrides.

Underwriters need to read PII and PII-adjacent data; they also write
claims and policies. The default mapping provides this; we add the
explicit data write privilege here for clarity.
"""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

INSURANCE_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.INSURANCE_UNDERWRITER: {
            Permission.WRITE_DATA,
            Permission.INVOKE_BILLING,
        },
    }
)
