"""Sales-ops vertical: end-to-end graph run with a scripted LLM."""
from __future__ import annotations

import pytest
from agentgraph_core.types import ToolCall
from agentgraph_llm.testing import ScriptedLLM, register_test_provider, response
from agentgraph_sales_ops import SalesOpsService
from agentgraph_sales_ops.tools import InMemoryCRM, set_crm


def setup_module() -> None:
    register_test_provider()


@pytest.mark.asyncio
async def test_sales_ops_qualifies_lead() -> None:
    register_test_provider()
    ScriptedLLM.reset()
    ScriptedLLM.script(
        "qualifier_agent",
        response(
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
        response(text="Qualified.", prompt_tokens=5, completion_tokens=2),
    )
    svc = SalesOpsService.default(llm_provider="test", llm_model="test-model")
    state = await svc.runner.arun(svc.lead_graph, input={"contact_email": "ada@analytix.com"})
    assert state.finished
    ScriptedLLM.reset()


def test_sales_ops_crm_seed() -> None:
    crm = InMemoryCRM()
    crm.seed([{"domain": "acme.com", "contacts": [{"name": "Eve", "email": "eve@acme.com"}]}])
    set_crm(crm)
    acct = crm.get(email="eve@acme.com")
    assert acct is not None
    assert acct.get("domain") == "acme.com"
