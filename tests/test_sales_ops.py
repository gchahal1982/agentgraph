"""Sales-ops vertical: end-to-end graph run with a scripted LLM."""
from __future__ import annotations

import pytest
from agentgraph_core.types import ToolCall
from agentgraph_llm.mock import MockLLM, mock_response
from agentgraph_sales_ops import SalesOpsService
from agentgraph_sales_ops.tools import InMemoryCRM, set_crm


@pytest.mark.asyncio
async def test_sales_ops_qualifies_lead() -> None:
    MockLLM.reset()
    # Script the qualifier agent to call crm_upsert and then return text.
    MockLLM.script(
        "qualifier_agent",
        mock_response(
            text="",
            tool_calls=[
                ToolCall(
                    id="t1",
                    name="crm_upsert",
                    arguments={"lead": {"id": "x", "email": "ada@analytix.com", "verdict": "sql"}},
                ),
            ],
            prompt_tokens=20,
            completion_tokens=10,
        ),
        mock_response(text="Qualified.", prompt_tokens=5, completion_tokens=2),
    )
    svc = SalesOpsService.default()
    result = svc.runner.arun(svc.lead_graph, input={"contact_email": "ada@analytix.com"})
    # The script includes upsert + a final answer; the agent's node loops
    # at most max_steps times. We just want to assert the graph executed
    # without error and produced a result.
    state = await result
    assert state.finished
    MockLLM.reset()


def test_sales_ops_crm_seed() -> None:
    crm = InMemoryCRM()
    crm.seed([{"domain": "acme.com", "contacts": [{"name": "Eve", "email": "eve@acme.com"}]}])
    set_crm(crm)
    acct = crm.get(email="eve@acme.com")
    assert acct is not None
    assert acct.get("domain") == "acme.com"
