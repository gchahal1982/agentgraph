"""Sales-ops role -> permission overrides.

Sales reps and SDRs need read access to PII (contact info) and network
access (to send email). Compliance officers reviewing the same data also
need read access but not network access.
"""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

SALES_OPS_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.SALES_REP: {
            Permission.READ_PII,
            Permission.INVOKE_BILLING,
            Permission.WRITE_DATA,
        },
    }
)
