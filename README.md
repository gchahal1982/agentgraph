# AgentGraph

**Agent runtime for business outcomes.** Open-source orchestration with packaged agents for sales ops, support ops, compliance, recruiting, insurance, construction, and healthcare.

[Docs](./docs) · [Quick start](#quick-start) · [Verticals](#verticals) · [Why AgentGraph?](#why-agentgraph) · [Architecture](#architecture) · [Contributing](./CONTRIBUTING.md) · [License](./LICENSE)

```
   ╭───────────────────────────────────────────────────────────────╮
   │  AgentGraph = Runtime + Vertical Packs + Compliance          │
   │                                                               │
   │   sales-ops    support-ops    compliance    recruiting        │
   │   insurance    construction   healthcare                     │
   │                                                               │
   │   All built on the same runtime: graph execution, durable     │
   │   checkpoints, audit log, RBAC, observability.                │
   ╰───────────────────────────────────────────────────────────────╯
```

## Why AgentGraph?

Agent orchestration frameworks are crowded and developer-heavy.
LangChain, AutoGen, CrewAI, Agno, MetaGPT, and AutoGPT each ship a
general-purpose toolbox. Business users don't want a toolbox — they
want outcomes.

AgentGraph ships **packaged agents for specific business outcomes**,
backed by a runtime that takes care of the things every production
agent needs:

- **Graph-based execution** with conditional routing and durable
  checkpoints. Resume a run hours or days later from its last
  checkpoint.
- **Audit log** that records every model call, tool call, and policy
  decision. Required for SOC2, HIPAA, and other regulated verticals.
- **RBAC** baked into the tool layer. Tools that touch PHI declare
  it; the runtime rejects calls without the right permission.
- **Human handoff** as a first-class transition. Tools can request
  handoff to a human; the run pauses, then resumes when the human
  replies.
- **Cost & token tracking** on every model call. Per-run and
  per-vertical breakdowns for FinOps.
- **Pluggable LLM providers**: OpenAI, Anthropic, Ollama, and any
  OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp).

## Quick start

### Install

```bash
# Requires Python 3.11+
pip install agentgraph-sales-ops    # or any other vertical
# Or install the whole workspace from source:
git clone https://github.com/anomalyco/agentgraph
cd agentgraph
uv sync --all-packages
```

### Configure (model + storage)

AgentGraph talks to a real LLM and persists state durably. Configure both via
environment (a starter `.env.example` is included):

```bash
# Model: provider + key. Fails fast at run time if the key is missing.
export AG_LLM_PROVIDER=openai           # openai | anthropic | ollama
export AG_LLM_MODEL=gpt-4o-mini
export OPENAI_API_KEY=sk-...

# Storage: durable by default. SQLite needs nothing; Postgres for multi-node.
export AG_STORAGE_URL="sqlite:///$HOME/.local/share/agentgraph/agentgraph.db"
# export AG_STORAGE_URL="postgresql://user:pass@host:5432/agentgraph"

# Server auth (required before exposing the API).
export AG_API_KEY="$(openssl rand -hex 32)"
```

With a local model and no API key, set `AG_LLM_PROVIDER=ollama` (and run
Ollama). The fake/scripted provider lives only in `agentgraph_llm.testing`
and is used by the test suite — it is never a silent production default.

### Run a packaged vertical

```python
from agentgraph_sales_ops import SalesOpsService

# Uses AG_LLM_PROVIDER/AG_LLM_MODEL + key, and AG_STORAGE_URL for durable state.
svc = SalesOpsService.default()
result = svc.run_lead(contact_email="ada@analytix.com")
print(result.output, result.cost_usd)
```

```bash
uv run ag-sales-ops --port 8081
curl -X POST http://localhost:8081/run/lead \
  -d '{"contact_email": "ada@analytix.com"}' \
  -H 'content-type: application/json'
```

### Or define your own graph

```python
from agentgraph_sdk import Agent, Graph
from agentgraph_sdk.runner import Runner
from agentgraph_core.tools import tool
from agentgraph_llm.base import default_llm_config

@tool(description="Look up a customer in the CRM")
async def get_customer(ctx, customer_id: str):
    return await crm.get(customer_id)

agent = Agent(
    name="support",
    description="Tier-1 support agent",
    system_prompt="You are a tier-1 support agent.",
    llm=default_llm_config(),     # resolves provider/model/key from env
    tools=[get_customer],
)

g = Graph("support")
g.add_agent(agent, entrypoint=True)

# Runner persists checkpoints + audit to AG_STORAGE_URL (durable by default).
result = Runner().run(g.compile(), input={"prompt": "Where is my order?"})
```

## Verticals

Each vertical is a self-contained Python package that ships:

- **A `Service`** with `default()` for one-line startup
- **Domain tools** (CRM lookup, ticket creation, EHR query, ...) with
  pluggable backends
- **A compiled `Graph`** for the canonical business flow
- **Prompts and policies** specific to the vertical
- **A FastAPI service** you can run standalone (`ag-sales-ops`, etc.)

| Vertical | Package | Service | Default port | Outcomes |
|---|---|---|---|---|
| Sales ops | `agentgraph-sales-ops` | `ag-sales-ops` | 8081 | Lead qualification, outreach, pipeline review |
| Support ops | `agentgraph-support-ops` | `ag-support-ops` | 8082 | Ticket triage, deflection, escalation |
| Compliance | `agentgraph-compliance` | `ag-compliance` | 8083 | Policy review, control mapping, evidence collection |
| Recruiting | `agentgraph-recruiting` | `ag-recruiting` | 8084 | Sourcing, screening, scheduling |
| Insurance | `agentgraph-insurance` | `ag-insurance` | 8085 | FNOL intake, underwriting copilot, claims triage |
| Construction | `agentgraph-construction` | `ag-construction` | 8086 | RFI drafting, submittal review, daily log |
| Healthcare | `agentgraph-healthcare` | `ag-healthcare` | 8087 | Intake triage, prior auth, discharge summary |

Each package's `README.md` documents the graph and tools.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  ui (Next.js dashboard)                                              │
│      │                                                              │
│      ▼                                                              │
│  server (FastAPI)   ──  cli (ag)                                     │
│      │                                                              │
│      ▼                                                              │
│  sdk (Agent, Graph, Runner)                                          │
│      │                                                              │
│      ▼                                                              │
│  runtime (graph execution, checkpoints, handoff)                     │
│      │                                                              │
│      ├─► core (tools, audit, rbac, observability, memory)            │
│      └─► llm (OpenAI, Anthropic, Ollama, Mock)                       │
│                                                                      │
│  verticals ─► sales-ops | support-ops | compliance | recruiting |    │
│              insurance | construction | healthcare                  │
└──────────────────────────────────────────────────────────────────────┘
```

- **`agentgraph-core`** — Primitives: agents, tools, audit, RBAC,
  observability, memory. ~800 LOC. No LLM-specific code.
- **`agentgraph-llm`** — Provider-agnostic LLM adapter. Pluggable
  registry. Includes `MockLLM` for tests and offline development.
- **`agentgraph-runtime`** — Graph execution engine. Nodes, edges,
  conditional routing, durable checkpoints, handoff.
- **`agentgraph-sdk`** — High-level API: `Agent`, `Graph`, `Runner`.
- **`agentgraph-server`** — FastAPI service exposing the runtime over
  HTTP.
- **`agentgraph-cli`** — Command-line interface: `ag serve`, `ag run`,
  `ag audit`.
- **`verticals/*`** — Business-ready packs, one per vertical. Each
  depends only on the public APIs of the lower layers.

## Development

```bash
make install   # uv sync --all-packages
make test      # ./scripts/test.sh (pytest in an isolated uv env)
make lint      # ruff
make typecheck # mypy
make serve     # launch server on :8080
```

The workspace uses [uv](https://github.com/astral-sh/uv) for fast,
deterministic installs. CI runs against Python 3.11 and 3.12.

> Tests run via `./scripts/test.sh`, which uses the frozen root development
> dependency group. This avoids a broken system-level pytest if one is present
> on your `PATH` and keeps local and CI tooling aligned.

## Configuration

All configuration is via environment variables.

| Variable | Purpose | Default |
|---|---|---|
| `AG_LLM_PROVIDER` | `openai`, `anthropic`, or `ollama` | `openai` |
| `AG_LLM_MODEL` | Model name | provider default (e.g. `gpt-4o-mini`) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider key | — (required for that provider) |
| `AG_STORAGE_URL` | `sqlite:///path.db` or `postgresql://...` | SQLite under the data dir |
| `AG_API_KEY` | Bearer token required by the HTTP API | — (required; server fails closed when unset) |
| `AG_ALLOW_INSECURE_NO_AUTH` | Explicitly allow unauthenticated local development | `0` (set to `1` locally only) |

`default_llm_config()` raises a clear error at run time if the selected
provider needs a key that is not set, so a misconfigured deployment fails
fast instead of producing silent or fake output.

## Security

- The HTTP server requires a bearer token (`AG_API_KEY`) on every privileged
  route. Health checks (`/healthz`, `/readyz`) are public for load balancers.
  Startup fails closed when `AG_API_KEY` is unset. For local-only development,
  you may explicitly set `AG_ALLOW_INSECURE_NO_AUTH=1`; never use that override
  on a host exposed to a network. If both variables are set, the API key takes
  precedence and authentication remains enabled.
- RBAC is enforced in the runtime: nodes that touch PII/PHI declare a required
  permission, and a run without a principal holding it is rejected.
- The audit log records every model call, tool call, and policy decision with
  the run id, thread id, and principal. Use a Postgres `AG_STORAGE_URL` (or a
  WORM-backed store) for tamper-evidence in regulated verticals.

## Tests

```bash
./scripts/test.sh            # all tests
./scripts/test.sh tests/test_runtime.py
# 39 passed
```

## Differentiators vs. CrewAI / AutoGen / LangGraph / LangChain

| | CrewAI | AutoGen | LangGraph | LangChain | **AgentGraph** |
|---|---|---|---|---|---|
| Packaged verticals | ❌ | ❌ | ❌ | ❌ | ✅ |
| Durable checkpoints | ❌ | ❌ | ✅ | partial | ✅ |
| RBAC + audit by default | ❌ | ❌ | ❌ | ❌ | ✅ |
| HIPAA / SOC2 ready | ❌ | ❌ | ❌ | ❌ | ✅ |
| Human handoff first-class | ❌ | partial | partial | ❌ | ✅ |
| Multi-tenant runtime | ❌ | ❌ | ❌ | ❌ | ✅ |
| LLM-agnostic | ✅ | ✅ | ✅ | ✅ | ✅ |
| Standalone services per vertical | ❌ | ❌ | ❌ | ❌ | ✅ |

## License

Apache 2.0. See [LICENSE](./LICENSE).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Issues and PRs welcome.
