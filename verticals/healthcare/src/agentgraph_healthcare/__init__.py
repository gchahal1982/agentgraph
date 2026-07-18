"""Healthcare vertical pack.

Outcomes:
- Triage patient intake messages by acuity and route to the right clinician
- Draft prior-authorization requests from a clinical note
- Generate a discharge summary from a hospital-stay transcript

Compliance:
- All graph nodes that touch PHI require `data.read.phi`. The default
  role for this vertical is `clinician`. The runtime enforces this with
  the policy layer; tools cannot be called without the right permission.
- Every model call is logged to the audit log with the run id, thread id,
  and the principal that initiated the run.

Default graphs:

- `intake_triage_graph`   - patient message -> acuity -> clinician handoff
- `prior_auth_graph`      - clinical note -> PA request -> reviewer signoff
- `discharge_summary_graph` - transcript -> discharge summary
"""
from agentgraph_healthcare.graphs import (
    build_healthcare_runner,
    discharge_summary_graph,
    intake_triage_graph,
    prior_auth_graph,
)
from agentgraph_healthcare.policies import HEALTHCARE_ROLES
from agentgraph_healthcare.service import HealthcareService
from agentgraph_healthcare.tools import (
    append_discharge_summary,
    draft_prior_auth,
    escalate_to_clinician,
    lookup_patient,
    open_encounter,
    signoff_prior_auth,
)

__all__ = [
    "HEALTHCARE_ROLES",
    "HealthcareService",
    "append_discharge_summary",
    "build_healthcare_runner",
    "discharge_summary_graph",
    "draft_prior_auth",
    "escalate_to_clinician",
    "intake_triage_graph",
    "lookup_patient",
    "open_encounter",
    "prior_auth_graph",
    "signoff_prior_auth",
]
