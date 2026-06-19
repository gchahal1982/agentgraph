# agentgraph-sales-ops

Sales operations vertical pack: lead qualification, outreach, pipeline review.

## Outcomes

- Qualify inbound leads against the ICP and assign a verdict (SQL / MQL / disqualified)
- Draft personalized outreach for sales reps
- Summarize an account's pipeline and propose next-best actions
- Route hot leads to a human rep via the handoff queue

## Quick start

```python
from agentgraph_sales_ops import SalesOpsService

svc = SalesOpsService.default()
result = svc.run_lead(contact_email="ada@analytix.com")
print(result.output, result.cost_usd)
```

## Standalone service

```bash
uv run ag-sales-ops --port 8081
curl -X POST http://localhost:8081/run/lead -d '{"contact_email": "ada@analytix.com"}' -H 'content-type: application/json'
```

## Graph

The default graph is `lead_qualification_graph`:

```
enrich -> score_and_qualify -> route_after_qualify
                                   |
                                   +-- sql   -> human_handoff
                                   +-- mql   -> draft_outreach -> notify_rep
                                   +-- other -> END
```

The `score_and_qualify` and `draft_outreach` nodes are LLM agents that
can call the CRM, score leads, draft emails, and hand off to a human.

## Tools

- `crm_lookup` / `crm_upsert` - pluggable CRM backend (default: in-memory)
- `score_lead` - deterministic 0-100 score
- `draft_email` - personalized cold email
- `handoff_to_rep` - routes the run to a human rep and signals transition

## Plug in your CRM

```python
from agentgraph_sales_ops import set_crm
from agentgraph_sales_ops.tools import InMemoryCRM

crm = InMemoryCRM()
crm.seed([{"domain": "acme.com", "name": "Acme", "contacts": [{"name": "Eve", "email": "eve@acme.com"}]}])
set_crm(crm)
```

For production, implement the `CRM` protocol in `tools.py` against
HubSpot, Salesforce, or Pipedrive.
