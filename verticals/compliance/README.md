# agentgraph-compliance

Compliance vertical pack: policy review, control mapping, evidence collection.

## Outcomes

- Map a control requirement to evidence in connected systems
- Draft policy diffs and review existing policies for gaps
- Generate audit-ready reports for SOC2, ISO 27001, HIPAA, GDPR
- Flag risks and route them to a compliance officer for sign-off

## Quick start

```python
from agentgraph_compliance import ComplianceService

svc = ComplianceService.default()
result = svc.review(control="CC6.1", framework="soc2")
print(result.output)
```

## Standalone service

```bash
uv run ag-compliance --port 8083
curl -X POST http://localhost:8083/run/review -d '{"control": "CC6.1"}' -H 'content-type: application/json'
curl -X POST http://localhost:8083/run/audit  -d '{"framework": "soc2"}' -H 'content-type: application/json'
```

## Graph

```
parse_request -> collect_evidence -> gap_analysis -> human_signoff
                                                  |
                                                  +-- all evidence attached -> signoff
                                                  +-- gaps -> flag_risk -> signoff (denied)
```

## Production wiring

The default `InMemoryEvidenceStore` is fine for development. For
production, implement the `EvidenceStore` protocol against Vanta, Drata,
or your GRC system of record. The runtime doesn't care; it only sees
`list(control)` and `attach(control, evidence)`.

## Audit trail

Every `signoff` and `flag_risk` call writes to the audit log. The
`ComplianceService` uses the default `InMemoryAuditLog`; production
deployments should wire it to a tamper-evident store (Postgres +
WORM bucket, or a service like AWS QLDB).
