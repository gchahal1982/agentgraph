# agentgraph-construction

Construction vertical pack: RFI drafting, submittal review, daily log.

## Outcomes

- Draft Requests for Information (RFIs) from free-text field notes
- Review submittals (shop drawings, product data) against the project spec
- Generate the daily log from crew inputs and weather
- Route blocked issues to the project manager

## Quick start

```python
from agentgraph_construction import ConstructionService

svc = ConstructionService.default()
result = svc.draft_rfi(
    field_notes="Slab thickness at column line C looks like 6\" not the 8\" called out in spec 03 30 00.",
    project_id="PRJ-001",
)
print(result.output)
```

## Standalone service

```bash
uv run ag-construction --port 8086
curl -X POST http://localhost:8086/run/rfi -d '{
  "field_notes": "Slab thickness looks short at column line C; spec 03 30 00 says 8\".",
  "project_id": "PRJ-001"
}' -H 'content-type: application/json'
```

## Graphs

- `rfi_drafting_graph` - intake -> draft RFI -> PM review
- `submittal_review_graph` - compare submittal to spec -> verdict
- `daily_log_graph` - compose the daily log

## Plug in your project system

The default `InMemoryProjectStore` is for development. For production,
implement the `ProjectStore` protocol against Procore, Autodesk Build, or
your internal project management system.
