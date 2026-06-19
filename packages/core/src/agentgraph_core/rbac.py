"""Role-based access control for tools and resources.

Vertical packs in regulated industries (healthcare, insurance) plug
principals and permissions into the runtime. Tools that touch PHI or PII
declare `requires_principal=True`; the runtime rejects calls without a
matching permission.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class Permission(str, Enum):
    # Data scopes
    READ_PUBLIC = "data.read.public"
    READ_PII = "data.read.pii"
    READ_PHI = "data.read.phi"  # protected health information
    WRITE_DATA = "data.write"
    # Action scopes
    INVOKE_TOOL = "tool.invoke"
    INVOKE_NETWORK = "network.invoke"
    INVOKE_BILLING = "billing.invoke"
    ADMIN = "admin"


class RbacRole(str, Enum):
    ANON = "anon"
    USER = "user"
    SUPPORT_AGENT = "support_agent"
    SALES_REP = "sales_rep"
    RECRUITER = "recruiter"
    COMPLIANCE_OFFICER = "compliance_officer"
    INSURANCE_UNDERWRITER = "insurance_underwriter"
    CLINICIAN = "clinician"
    CONSTRUCTION_PM = "construction_pm"
    ADMIN = "admin"


# Default role -> permission mapping. Vertical packs may override.
DEFAULT_ROLE_PERMISSIONS: dict[RbacRole, set[Permission]] = {
    RbacRole.ANON: {Permission.READ_PUBLIC},
    RbacRole.USER: {Permission.READ_PUBLIC, Permission.INVOKE_TOOL},
    RbacRole.SUPPORT_AGENT: {
        Permission.READ_PUBLIC,
        Permission.READ_PII,
        Permission.INVOKE_TOOL,
        Permission.INVOKE_NETWORK,
    },
    RbacRole.SALES_REP: {
        Permission.READ_PUBLIC,
        Permission.READ_PII,
        Permission.INVOKE_TOOL,
        Permission.INVOKE_NETWORK,
        Permission.INVOKE_BILLING,
    },
    RbacRole.RECRUITER: {
        Permission.READ_PUBLIC,
        Permission.READ_PII,
        Permission.INVOKE_TOOL,
        Permission.INVOKE_NETWORK,
    },
    RbacRole.COMPLIANCE_OFFICER: {
        Permission.READ_PUBLIC,
        Permission.READ_PII,
        Permission.INVOKE_TOOL,
        Permission.ADMIN,
    },
    RbacRole.INSURANCE_UNDERWRITER: {
        Permission.READ_PUBLIC,
        Permission.READ_PII,
        Permission.INVOKE_TOOL,
        Permission.INVOKE_NETWORK,
        Permission.WRITE_DATA,
    },
    RbacRole.CLINICIAN: {
        Permission.READ_PUBLIC,
        Permission.READ_PII,
        Permission.READ_PHI,
        Permission.WRITE_DATA,
        Permission.INVOKE_TOOL,
        Permission.INVOKE_NETWORK,
    },
    RbacRole.CONSTRUCTION_PM: {
        Permission.READ_PUBLIC,
        Permission.WRITE_DATA,
        Permission.INVOKE_TOOL,
        Permission.INVOKE_NETWORK,
    },
    RbacRole.ADMIN: {p for p in Permission},
}


class Principal(BaseModel):
    """The caller of a run. Tools may inspect `principal_id` to scope data access."""

    id: str
    roles: list[RbacRole] = []
    attributes: dict[str, Any] = {}

    def permissions(self, role_map: dict[RbacRole, set[Permission]] | None = None) -> set[Permission]:
        role_map = role_map or DEFAULT_ROLE_PERMISSIONS
        out: set[Permission] = set()
        for r in self.roles:
            out |= role_map.get(r, set())
        return out

    def has(self, perm: Permission, role_map: dict[RbacRole, set[Permission]] | None = None) -> bool:
        return perm in self.permissions(role_map)
