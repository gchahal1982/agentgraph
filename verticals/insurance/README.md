# agentgraph-insurance

Insurance vertical pack: FNOL intake, underwriting copilot, claims triage.

## Outcomes

- Capture First Notice of Loss (FNOL) from a customer description
- Triage claims by severity and route to the right adjuster
- Underwriting copilot: score risk and draft decision rationale
- Compliance-first: every decision is recorded in the audit log

## Quick start

```python
from agentgraph_insurance import InsuranceService

svc = InsuranceService.default()
result = svc.capture_fnol(
    description="My car was rear-ended at a stoplight on May 5. Bumper damage.",
    policy_id="POL-1001",
)
print(result.output, result.cost_usd)
```

## Standalone service

```bash
uv run ag-insurance --port 8085
curl -X POST http://localhost:8085/run/fnol -d '{
  "description": "My car was rear-ended on May 5.",
  "policy_id": "POL-1001"
}' -H 'content-type: application/json'
```

## Graphs

- `fnol_intake_graph` - capture loss details, score risk, route to adjuster
- `underwriting_copilot_graph` - score applicant risk, draft decision rationale
- `claims_triage_graph` - reorder open claims by risk and assign adjusters

## Compliance

All tool calls go through the runtime's policy layer (`INSURANCE_ROLES`).
The `escalate_to_human` tool signals a transition out of the agent node
so high-risk claims always reach a licensed underwriter.
