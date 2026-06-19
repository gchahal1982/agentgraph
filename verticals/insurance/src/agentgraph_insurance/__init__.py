"""Insurance vertical pack.

Outcomes:
- Capture First Notice of Loss (FNOL) from a customer description
- Triage claims by severity and route to the right adjuster
- Underwriting copilot: score risk and draft decision rationale
- Compliance-first: every decision is recorded in the audit log

Default graphs:

- `fnol_intake_graph`        - capture loss details, triage severity
- `underwriting_copilot_graph` - score risk, draft rationale
- `claims_triage_graph`      - route claims to the right adjuster
"""
from agentgraph_insurance.graphs import (
    build_insurance_runner,
    claims_triage_graph,
    fnol_intake_graph,
    underwriting_copilot_graph,
)
from agentgraph_insurance.policies import INSURANCE_ROLES
from agentgraph_insurance.service import InsuranceService
from agentgraph_insurance.tools import (
    assign_adjuster,
    escalate_to_human,
    lookup_policy,
    open_claim,
    score_risk,
    update_claim,
)

__all__ = [
    "open_claim",
    "update_claim",
    "score_risk",
    "lookup_policy",
    "assign_adjuster",
    "escalate_to_human",
    "fnol_intake_graph",
    "underwriting_copilot_graph",
    "claims_triage_graph",
    "build_insurance_runner",
    "INSURANCE_ROLES",
    "InsuranceService",
]
