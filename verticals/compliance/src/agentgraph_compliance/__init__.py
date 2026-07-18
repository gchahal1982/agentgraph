"""Compliance vertical pack.

Outcomes:
- Map a control requirement to evidence in connected systems
- Draft policy diffs and review existing policies for gaps
- Generate audit-ready reports for SOC2, ISO 27001, HIPAA, GDPR
- Flag risks and route them to a compliance officer for sign-off

Default graph `policy_review_graph`:

1. `parse_request`     - extract the control framework + scope
2. `collect_evidence`  - pull evidence from connected systems
3. `gap_analysis`      - LLM agent analyzes gaps
4. `human_signoff`     - route to compliance officer for review
"""
from agentgraph_compliance.graphs import (
    audit_report_graph,
    build_compliance_runner,
    policy_review_graph,
)
from agentgraph_compliance.policies import COMPLIANCE_ROLES
from agentgraph_compliance.service import ComplianceService
from agentgraph_compliance.tools import (
    attach_evidence,
    fetch_evidence,
    flag_risk,
    list_controls,
    signoff,
)

__all__ = [
    "COMPLIANCE_ROLES",
    "ComplianceService",
    "attach_evidence",
    "audit_report_graph",
    "build_compliance_runner",
    "fetch_evidence",
    "flag_risk",
    "list_controls",
    "policy_review_graph",
    "signoff",
]
