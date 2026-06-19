# agentgraph-support-ops

Support operations vertical pack: ticket triage, deflection, escalation.

## Outcomes

- Triage inbound tickets (intent, urgency, sentiment, topic)
- Deflect common questions to the self-serve knowledge base
- Suggest a reply for the human agent to send
- Escalate to a human when sentiment drops or urgency is high

## Quick start

```python
from agentgraph_support_ops import SupportOpsService

svc = SupportOpsService.default()
result = svc.triage_ticket("My dashboard is broken and I want a refund!")
print(result.output, result.cost_usd)
```

## Standalone service

```bash
uv run ag-support-ops --port 8082
curl -X POST http://localhost:8082/run/triage -d '{
  "message": "How do I reset my password?"
}' -H 'content-type: application/json'
```

## Graph

```
intake -> triage -> route_after_triage
                       |
                       +-- question + kb_hit -> deflect
                       +-- urgent | low sentiment -> escalate
                       +-- otherwise -> draft_reply -> await_human
```

## Plug in your KB and ticketing

```python
from agentgraph_support_ops import set_kb, set_ticketing
from agentgraph_support_ops.tools import InMemoryKB, InMemoryTicketing

set_kb(InMemoryKB())
set_ticketing(InMemoryTicketing())
```

For production, implement the `KnowledgeBase` and `Ticketing` protocols
against Zendesk, Intercom, or your internal systems.
