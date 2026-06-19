# agentgraph-healthcare

Healthcare vertical pack: intake triage, prior authorization, discharge summary.

## Outcomes

- Triage patient intake messages by acuity and route to the right clinician
- Draft prior-authorization requests from a clinical note
- Generate a discharge summary from a hospital-stay transcript

## Compliance

- Every tool that touches PHI declares `requires_principal=True`. The
  runtime enforces PHI access via `Permission.READ_PHI` on the
  principal. Without a clinician principal, calls are rejected.
- Every model call, tool call, and policy decision is recorded in the
  audit log with the run id, thread id, and principal id.
- The default role for this vertical is `clinician`. Patient-portal and
  back-office roles default to PII-only access.

## Quick start

```python
from agentgraph_healthcare import HealthcareService

svc = HealthcareService.default()
result = svc.triage(
    patient_id="pat_001",
    message="I've had chest pain for 30 minutes and feel short of breath.",
)
print(result.output)
```

## Standalone service

```bash
uv run ag-healthcare --port 8087
curl -X POST http://localhost:8087/run/intake -d '{
  "patient_id": "pat_001",
  "message": "I have chest pain and feel short of breath."
}' -H 'content-type: application/json'
```

## Graphs

- `intake_triage_graph`   - patient message -> acuity -> clinician handoff
- `prior_auth_graph`      - clinical note -> PA request -> signoff
- `discharge_summary_graph` - transcript -> discharge summary

## Plug in your EHR

The default `InMemoryPatientStore` is for development. For production,
implement the `PatientStore` protocol against Epic, Cerner, or Athena
via FHIR or the vendor's API. The runtime doesn't care which.
