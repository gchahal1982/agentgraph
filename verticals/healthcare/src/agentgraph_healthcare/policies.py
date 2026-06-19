"""Healthcare role overrides.

Clinicians need PHI access (data.read.phi) by default; non-clinical
users (e.g. patient portals, schedulers) get only PII. The runtime
enforces these scopes via the policy layer on every tool call.
"""
from __future__ import annotations

from agentgraph_core.rbac import Permission, RbacRole
from agentgraph_verticals.base import with_role

HEALTHCARE_ROLES: dict[RbacRole, set[Permission]] = with_role(
    {
        RbacRole.CLINICIAN: {
            Permission.WRITE_DATA,
            Permission.INVOKE_BILLING,
        },
    }
)
