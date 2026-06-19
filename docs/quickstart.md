# AgentGraph quickstart

This quickstart gets you from `git clone` to a running sales-ops
agent in under five minutes.

## 1. Clone and install

```bash
git clone https://github.com/anomalyco/agentgraph
cd agentgraph
uv sync --all-packages
```

If you don't have `uv`, install it: `pip install uv`.

## 2. Run an example without API keys

Every vertical ships with a `MockLLM` setup so you can run end-to-end
without an OpenAI key:

```bash
uv run --all-packages python examples/sales_ops/qualify_lead.py
```

You should see output like:

```
run_id=run_... finished=True cost_usd=0.0 tokens=12
output: {'account': {...}, 'qualification': 'sql'}
```

## 3. Run a vertical service

```bash
uv run ag-sales-ops --port 8081 &
curl -X POST http://localhost:8081/run/lead \
  -d '{"contact_email": "ada@analytix.com"}' \
  -H 'content-type: application/json' | jq
```

## 4. Plug in a real LLM

Set `AG_SALES_LLM_PROVIDER=openai` (or `anthropic`, `ollama`) and
`AG_SALES_LLM_MODEL=gpt-4o-mini`. Provide your API key in
`OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`).

```bash
export AG_SALES_LLM_PROVIDER=openai
export AG_SALES_LLM_MODEL=gpt-4o-mini
export OPENAI_API_KEY=sk-...
uv run ag-sales-ops --port 8081
```

## 5. Customize for your business

Each vertical exposes a `Service.default()` and accepts a custom CRM,
KB, ticketing system, etc. via `set_*` functions.

```python
from agentgraph_sales_ops import SalesOpsService
from agentgraph_sales_ops.tools import set_crm
from my_crm import HubSpotCRM

crm = HubSpotCRM(api_key="...")
set_crm(crm)

svc = SalesOpsService.default()
result = svc.run_lead(contact_email="ada@analytix.com")
```

## 6. Embed in your own app

The runtime is plain Python. Import what you need and use it directly:

```python
from agentgraph_runtime.runtime import Runtime
from agentgraph_healthcare.graphs import intake_triage_graph
from agentgraph_core.rbac import Principal, RbacRole

graph, agents = intake_triage_graph()
state = await Runtime().run(
    graph,
    input={"patient_id": "pat_001", "message": "I have chest pain."},
    principal=Principal(id="rn_42", roles=[RbacRole.CLINICIAN]),
)
```

## Next steps

- Read the [architecture doc](./architecture.md).
- Browse the vertical READMEs in `verticals/*/README.md`.
- Look at `examples/` for runnable demos.
- Spin up the UI: `cd ui && pnpm dev` (once published).
