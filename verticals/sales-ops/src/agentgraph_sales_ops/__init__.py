"""Sales operations vertical pack.

Outcomes:
- Qualify inbound leads against the ICP and assign a score
- Draft personalized outreach (email, LinkedIn) for sales reps
- Summarize account activity and propose next-best actions
- Route hot leads to a human rep via the handoff queue

The default `Graph` is `lead_qualification_graph`; it runs four nodes:
1. `enrich_lead`         - CRM enrichment (firmographics + intent)
2. `score_and_qualify`   - LLM decides MQL/SQL/disqualified + score
3. `draft_outreach`      - LLM drafts email/LinkedIn if MQL
4. `handoff`             - routes to a human rep if score >= threshold
"""
from agentgraph_sales_ops.graphs import (
    build_sales_ops_runner,
    lead_qualification_graph,
    pipeline_summary_graph,
)
from agentgraph_sales_ops.policies import SALES_OPS_ROLES
from agentgraph_sales_ops.service import SalesOpsService
from agentgraph_sales_ops.tools import (
    crm_lookup,
    crm_upsert,
    draft_email,
    handoff_to_rep,
    score_lead,
)

__all__ = [
    "crm_lookup",
    "crm_upsert",
    "score_lead",
    "draft_email",
    "handoff_to_rep",
    "lead_qualification_graph",
    "pipeline_summary_graph",
    "build_sales_ops_runner",
    "SALES_OPS_ROLES",
    "SalesOpsService",
]
