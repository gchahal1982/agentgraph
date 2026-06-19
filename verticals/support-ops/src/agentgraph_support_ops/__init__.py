"""Support operations vertical pack.

Outcomes:
- Triage incoming tickets (intent, urgency, sentiment, topic)
- Deflect common questions to the self-serve knowledge base
- Suggest a response for the human agent to send
- Escalate to a human when sentiment drops or PII is involved

Default graph `ticket_triage_graph`:

1. `intake`          - normalize the ticket
2. `classify`        - LLM agent classifies and decides routing
3. `deflect`         - returns a self-serve answer if known
4. `draft_reply`     - LLM drafts a reply for the human to send
5. `escalate`        - hands off to a human queue
"""
from agentgraph_support_ops.graphs import (
    build_support_ops_runner,
    csat_loop_graph,
    ticket_triage_graph,
)
from agentgraph_support_ops.policies import SUPPORT_OPS_ROLES
from agentgraph_support_ops.service import SupportOpsService
from agentgraph_support_ops.tools import (
    escalate_to_human,
    kb_add_article,
    kb_search,
    sentiment_score,
    ticket_create,
    ticket_update,
)

__all__ = [
    "kb_search",
    "kb_add_article",
    "ticket_create",
    "ticket_update",
    "sentiment_score",
    "escalate_to_human",
    "ticket_triage_graph",
    "csat_loop_graph",
    "build_support_ops_runner",
    "SUPPORT_OPS_ROLES",
    "SupportOpsService",
]
