# AgentGraph quickstart

From `git clone` to a running, authenticated agent server.

## 1. Clone and install

```bash
git clone https://github.com/anomalyco/agentgraph
cd agentgraph
uv sync --all-packages
```

If you don't have `uv`, install it: `pip install uv`.

## 2. Configure a model and storage

AgentGraph calls a real LLM and persists state durably. Copy the example env
and fill in a provider key:

```bash
cp .env.example .env
# edit .env: set AG_LLM_PROVIDER, AG_LLM_MODEL, OPENAI_API_KEY, AG_API_KEY
set -a; source .env; set +a
```

- **Hosted model:** `AG_LLM_PROVIDER=openai`, `AG_LLM_MODEL=gpt-4o-mini`,
  `OPENAI_API_KEY=sk-...`
- **Local model (no key):** run [Ollama](https://ollama.com), then
  `AG_LLM_PROVIDER=ollama`, `AG_LLM_MODEL=llama3.3`.
- **Storage:** defaults to a SQLite file. For multi-node, set
  `AG_STORAGE_URL=postgresql://...`.

If a hosted provider is selected without its key, AgentGraph fails fast with a
clear error rather than running against a misconfigured backend.

## 3. Run a vertical service

```bash
uv run ag-sales-ops --port 8081 &
curl -X POST http://localhost:8081/run/lead \
  -d '{"contact_email": "ada@analytix.com"}' \
  -H 'content-type: application/json' | jq
```

## 4. Run the multi-vertical server (authenticated)

The server registers every installed vertical's agents at startup and runs
them over HTTP. It requires `AG_API_KEY`:

```bash
export AG_API_KEY="$(openssl rand -hex 32)"
uv run agentgraph-server &

# Health checks are public:
curl localhost:8080/healthz

# Privileged routes require the bearer token:
TID=$(curl -s -XPOST localhost:8080/threads -H "Authorization: Bearer $AG_API_KEY" | jq -r .thread_id)
curl -s -XPOST localhost:8080/threads/$TID/run \
  -H "Authorization: Bearer $AG_API_KEY" -H 'content-type: application/json' \
  -d '{"agent":"qualify_lead","input":{"contact_email":"ada@analytix.com"}}' | jq
```

## 5. Customize for your business

Each vertical exposes `Service.default(llm_provider=..., llm_model=...,
storage_url=...)` and accepts a custom CRM, KB, ticketing system, EHR, etc.
via `set_*` injectors:

```python
from agentgraph_sales_ops import SalesOpsService
from agentgraph_sales_ops.tools import set_crm
from my_crm import HubSpotCRM   # implements the CRM protocol

set_crm(HubSpotCRM(api_key="..."))
svc = SalesOpsService.default()           # uses env for model + storage
result = svc.run_lead(contact_email="ada@analytix.com")
```

## 6. Embed the runtime in your own app

```python
from agentgraph_healthcare.graphs import intake_triage_graph
from agentgraph_sdk.runner import Runner
from agentgraph_core.rbac import Principal, RbacRole

graph, agents = intake_triage_graph()     # LLM resolved from env at run time
runner = Runner(principal=Principal(id="rn_42", roles=[RbacRole.CLINICIAN]))
result = await runner.arun(graph, input={"patient_id": "pat_001", "message": "chest pain"})
```

## 7. Run the tests

```bash
./scripts/test.sh        # 39 passed
```

## Next steps

- Read the [architecture doc](./architecture.md).
- Browse the vertical READMEs in `verticals/*/README.md`.
- Look at `examples/` for runnable demos (offline by default).
- Spin up the dashboard: `cd ui && pnpm dev`.
