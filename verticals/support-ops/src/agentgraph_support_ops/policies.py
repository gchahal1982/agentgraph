"""Support-ops role overrides.

Support agents need read access to PII (customer contact info) and
network access (to fetch external services when needed). The default
mapping already provides this; here we add any vertical-specific grants.
"""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

SUPPORT_OPS_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.SUPPORT_AGENT: {
            Permission.WRITE_DATA,
        },
    }
)
