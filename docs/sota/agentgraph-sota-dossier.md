# AgentGraph state-of-the-art dossier

**Assessment cutoff:** 2026-07-18
**Repository:** https://github.com/gchahal1982/agentgraph
**Assessed revision:** `f4f88b29298cd2d5121c6e27588af210e04e86c0` plus the local remediation working tree on `vorflux/agentgraph-sota-20260718`
**Verdict:** **Not Yet SOTA**
**Confidence:** High for repository findings; medium for fast-moving competitor capability comparisons; low for unpublished commercial operating characteristics.

## Executive finding

AgentGraph is a compact, understandable Python agent orchestration prototype with useful foundations: typed graph construction, conditional routing, SQLite/Postgres checkpoints, an audit abstraction, node-level RBAC, three model-provider paths, a FastAPI service, a CLI/SDK, seven domain packs, Docker Compose, and a small Next.js dashboard. The current code is unusually broad for its size and the vertical-pack strategy is a credible product differentiation.

It is not presently state of the art. Critical gates fail on durable-execution semantics, human approval, identity and tenant isolation, audit completeness, production observability and evaluation, distributed execution, interoperability, release proof, and matched comparative evidence. Several prominent repository claims are not supported by the implementation: the runtime does not emit audit records for every model/tool call; `Tool.requires_principal` is not enforced by `Tool.__call__`; handoff types and routing exist but are not integrated into runtime pause/resolve/resume; the API lets a bearer-token holder self-assert roles; and Postgres persistence does not provide worker leases, idempotency, or exactly-once/at-least-once execution controls.

The local remediation is real but does not change this verdict. It adds a pinned root `dev` dependency group and corresponding lock entries, moves FastAPI's `RunBody` to module scope to fix body-model/schema behavior, and removes a malformed duplicate exception block. The working tree also contains lint-only export/slot ordering and whitespace changes. A fresh runtime run reportedly passed **81 tests before lint** in the current remediation session; that result is session-reported and has no retained run artifact in the repository, so independent reproduction is **unverified**. Full lint and SOTA verification are being rerun by the main agent and are **pending**, not passed.

## 1. Category and scope

### 1.1 Category definition

An **agent orchestration runtime** is the execution and control layer that turns model calls, tools, state, and agent delegation into reliable, governable, observable, long-running applications. A frontier product in this category should cover:

1. expressive agent/workflow composition;
2. durable, deterministic recovery with explicit delivery semantics;
3. safe human interruption, approval, amendment, and resumption;
4. production scheduling, concurrency, retries, cancellation, and distributed workers;
5. identity-bound authorization, isolation, secrets, policy, and audit;
6. traces, metrics, evaluation, replay, and cost/quality controls;
7. open model/tool/protocol interoperability;
8. deployability, upgrade safety, operational tooling, and credible adoption evidence.

This definition distinguishes orchestration runtimes from adjacent products:

- **Agent SDKs/frameworks** supply programming primitives but may delegate durability and operations elsewhere.
- **Durable workflow engines** such as Temporal supply stronger execution guarantees but are not agent-specific.
- **Low-code agent platforms** such as Dify optimize authoring, integrations, and application delivery.
- **Managed agent services/control planes** such as LangSmith Deployment, Microsoft Foundry Agent Service, Vertex AI Agent Engine, and Amazon Bedrock Agents add hosted operations and governance.
- **Observability/evaluation products** can complement any runtime and are not substitutes for execution semantics.

### 1.2 Evaluation boundary

Included: all 201 tracked files present at the assessed revision, current uncommitted remediation, runtime/core/SDK/server/CLI/LLM packages, seven vertical packages, examples, tests, Docker/Compose, UI, CI, and the SOTA evidence framework. Binary favicon content was inventoried but is not capability-bearing. Generated caches and `.venv` were excluded.

The repository scan covered approximately 17,772 rendered text lines (including `uv.lock` and JSON schemas), 117 tracked Python files, all package manifests, all workflows, all tests, and all current diffs. The repository had 13 commits and two author identities at cutoff. These are descriptive facts, not quality proxies.

Excluded from demonstrated capability: README promises without executable evidence, hypothetical production adapters, hosted services not present here, compliance certifications, performance/scalability claims without benchmark artifacts, and the main agent's still-running lint/SOTA verification.

## 2. Method and hard gates

### 2.1 Evidence scale

The repository's own SOTA contract uses 0–4 anchors: 0 absent/contradicted, 1 interface/claim/manual prototype, 2 deterministic happy path, 3 representative integration/failure/security evidence, and 4 independently reproducible frontier-equivalent or leading behavior. It also discounts evidence by tier (`code-inspection` 0.45, deterministic unit 0.65, integration contract 0.85, independent/live 1.0). See `scripts/sota/score.py`.

This dossier uses the same conceptual anchors but does **not** claim to be the canonical machine-generated score. Product-level `scope.json`, `criteria.json`, `claims.json`, `gaps.json`, comparator snapshots, matched run artifacts, and `verdict.json` are absent. The current verifier therefore operates in `portfolio-skeleton` mode. Any numeric score below is a prioritization diagnostic, not proof of SOTA.

### 2.2 Critical evidence gates

A SOTA verdict requires every gate below to pass. Unknown evidence cannot pass a gate.

| Gate | Requirement | Current result | Evidence |
|---|---|---:|---|
| G1 Reproducible release | Clean checkout, pinned toolchain, build/lint/type/test/security/SOTA checks, retained artifacts, tested SHA | **Fail** | Root dev pins are remediated locally, but lint/SOTA rerun is pending; CI uses `setup-uv@v3` with `latest`; mypy is non-blocking; no release artifact or SBOM/provenance |
| G2 Durable correctness | Crash recovery, retries, cancellation, idempotency, concurrency control, replay/upgrade semantics, fault-injection proof | **Fail** | Per-node checkpoints exist; the rest is absent or unverified |
| G3 Human control | Persisted interrupt, approval queue, authenticated reviewer, edit/reject/timeout/escalate, safe resume | **Fail** | Handoff datatypes exist; runtime/API integration is absent |
| G4 Security/governance | Identity-bound roles, deny-path audit, tenant isolation, secrets controls, threat model, security tests | **Fail** | Shared bearer auth and node RBAC exist; caller-supplied roles, open mode, no tenancy/security suite |
| G5 Audit/observability | Complete model/tool/policy lifecycle telemetry, OTel export, trace correlation, redaction, evals, retained proof | **Fail** | Node spans and partial audit exist; README's complete-audit claim is contradicted by code |
| G6 Frontier comparison | Frozen universe, matched protocols, top sets, non-inferiority/lead evidence against every top comparator | **Fail** | No product evidence roots or matched benchmark runs |
| G7 Production operations | Distributed workers, queue/backpressure, schedules, deployment/rollback, migration, SLO/load/chaos evidence | **Fail** | Compose and persistence adapters only |
| G8 Ecosystem/interoperability | Broad providers plus MCP/A2A or equivalent, extension contracts, compatibility tests | **Fail** | OpenAI-compatible/Anthropic/Ollama paths; no MCP/A2A and limited integration tests |

Because all eight gates must pass and none demonstrably does, the only defensible label is **Not Yet SOTA**.

## 3. Repository evidence

### 3.1 Demonstrated architecture

| Area | Current implementation | Evidence quality | Important limits |
|---|---|---|---|
| Graph model | `GraphBuilder`, typed `Node`/`NodeResult`, static and conditional edges, compile-time endpoint validation, cycles bounded by `max_total_steps` | Code + unit tests | Sequential execution only; no fan-out/join, subgraph protocol, graph versioning, migration, cancellation, or visualization contract |
| Runtime | Async graph loop, state updates, errors, max-step guard, node spans | Code + unit tests | No retries despite `AuditAction.RETRY`; no timeouts, cancellation, queue, workers, schedules, leases, idempotency keys, or deterministic replay |
| Checkpoints | In-memory, SQLite WAL, and asyncpg/Postgres stores; snapshot after each completed node; resume latest checkpoint by thread | Code + SQLite tests; Postgres implementation inspection | Postgres integration/failure tests unverified; no transaction coupling to side effects/audit, locking, fencing, lease ownership, schema migration, checkpoint compatibility, or exact delivery contract |
| State | Pydantic run/graph/message state serialized through `orjson` | Code + tests | Arbitrary state evolution/versioning and secret/PII redaction are absent |
| Agent loop | Model/tool loop with schema-exposed tools, ordered calls, cost/token accumulation, `__goto__` transition | Code + LLM tests | No parallel calls, tool timeout/retry/idempotency, model fallback/routing, budget enforcement, guardrails, streaming, or model-call audit event |
| Tools | Pydantic-generated JSON schema and normalized `ToolResult` errors | Code + tests | `requires_principal` is metadata only in `Tool.__call__`; no sandbox, network policy, per-tool credentials, approval policy, or tool-call audit event |
| Handoff | `Handoff`, `HandoffChannel`, and `HandoffRouter` interfaces; vertical tools can set `__goto__` | Interface/code inspection | Runtime never constructs/routes/waits on a `Handoff`; no persisted approval object or API resolve endpoint; dashboard's resume statement is unsupported |
| RBAC | Enumerated roles/permissions and node-level `requires` enforcement; allow decisions audited | Code + unit test | Caller can self-assert any role in request body; deny decisions are not audited because exceptions occur before audit; no external identity, resource/tenant scope, policy engine, or role administration |
| Audit | In-memory, SQLite, Postgres append/query abstractions; run start/end, errors, and successful policy decision events | Code + tests | Model/tool/handoff/retry events are defined but not emitted by runtime/agent/tool paths; SQLite uses `INSERT OR REPLACE`; no immutability, hash chain/signing, retention/redaction/export, or deny audit |
| Observability | Nested in-process span model and structured log tracer; node duration/status | Code inspection | No actual OpenTelemetry exporter/dependency, collector config, metrics, dashboards, trace storage, model/tool spans, sampling, redaction, or evaluation linkage |
| Memory | Interface, in-memory substring search, thread buffer | Code inspection | Not integrated into runtime agent path; no durable/vector implementation, embeddings, policy, provenance, quality tests, or lifecycle controls |
| LLMs | OpenAI-compatible, Anthropic, Ollama; registry and explicit test provider | Code + mocked tests | No provider conformance suite with live endpoints; no streaming, multimodal proof, structured-output contract, fallback/routing, cache, rate control, or provider breadth comparable to leaders |
| SDK/CLI/API | Python SDK, `Runner`, CLI, FastAPI health/agent/thread/run/audit endpoints, bearer auth | Code + TestClient end-to-end test | No run status/cancel/resume/approve/stream endpoint; no pagination beyond audit limit; raw exception details returned as HTTP 500; no API versioning, idempotency key, quotas, webhooks, or generated clients |
| Verticals | Seven installable packs: sales ops, support ops, compliance, recruiting, insurance, construction, healthcare; protocols and in-memory demo stores | Code + tests/examples | Packaged workflows are differentiated but production CRM/EHR/ATS/GRC/ticketing/project connectors are only suggested; outcome quality, safety, compliance, and real-system integration are unverified |
| UI | Basic agents, run form, and audit pages | Code inspection | `useThreads()` calls `GET /api/threads`, while backend has no `GET /threads`; no approval inbox, graph authoring, trace view, evals, auth UX, or robust error handling |
| Deployment | Dockerfiles, Compose with Postgres/server/seven services/UI, health endpoints | Static config | Images/tool installs are not digest pinned; containers run as root; no migrations, Kubernetes/Helm, autoscaling, rolling upgrade, backup/restore, secrets manager, or production test |
| Quality system | 66 test functions visible in tracked tests; CI for Python 3.11/3.12; separate SOTA schemas/scripts/tests/workflows | Code inspection + session-reported run | CI typecheck is explicitly non-blocking; primary CI test invocation is narrow/ambiguous; no coverage threshold, mutation/fuzz/load/chaos/security tests; current full checks pending |
| Licensing/community | Apache-2.0 text in `LICENSE`; public GitHub repository | File/API | GitHub API reported `NOASSERTION`; 0 stars/forks/watchers at cutoff; no published governance, support policy, security policy, changelog, or adoption proof |

### 3.2 Claim reconciliation

| Repository claim | Finding |
|---|---|
| “Resume a run hours or days later from its last checkpoint” | SQLite/Postgres state can persist for that duration, but long-delay recovery, upgrades, credential expiry, timer behavior, and fault recovery are **unverified**. Resume is a direct library method, not an authenticated API lifecycle. |
| “Audit log records every model call, tool call, and policy decision” | **Contradicted.** Runtime emits run start/end, error, and successful node policy events. `AgentNode` and `Tool` do not write model/tool audit events. |
| “RBAC baked into the tool layer” | **Partially contradicted.** Runtime enforces `Node.requires`; `Tool.requires_principal` is not enforced in `Tool.__call__`. API roles are self-asserted by the bearer-token caller. |
| “Human handoff as a first-class transition” | **Interface/prototype only.** Graph transitions can target handoff-like nodes, but no durable interrupt/approval/response lifecycle is integrated. |
| “OpenTelemetry” / “OTel spans” | **Unverified as OTel.** The repository has its own span abstraction and structured logging, not an OpenTelemetry SDK/exporter implementation. |
| “Multi-tenant runtime” | **Contradicted by current code.** There is no tenant identifier, tenant-bound query, row-level isolation, quota, or identity mapping. |
| “HIPAA / SOC2 ready” | **Unverified.** No certification, BAA, controls mapping, security assessment, data-flow/redaction controls, or compliance test evidence is present. |
| “Production deployments use Postgres + WORM/QLDB” | Postgres adapters exist; WORM/QLDB integration is advice only and **unverified**. |
| “Standalone services per vertical” | Demonstrated as package entry points/Dockerfiles and covered in tests at a basic level. Production readiness is **unverified**. |

### 3.3 Present remediation and validation state

| Item | Current evidence | Status |
|---|---|---|
| Root developer dependencies | `pyproject.toml` now pins `jsonschema==4.25.1`, `pytest==8.4.1`, `pytest-asyncio==0.24.0`, `referencing==0.36.2`, and `ruff==0.12.4`; `uv.lock` contains the group and transitive packages | Implemented locally |
| FastAPI body model | `RunBody` moved from inside `create_app()` to module scope, preserving fields and defaults | Implemented locally |
| Duplicate exception cleanup | Malformed duplicate `except Exception` block in vertical registration removed | Implemented locally |
| Lint-only cleanup | Export arrays, `__slots__`, and one blank line reordered/adjusted across local source files | Implemented locally; no capability change |
| Runtime tests | 81 tests reportedly passed before lint in the current remediation run | Session-reported; retained log/hash **unverified** |
| Full lint and SOTA verification | Main agent is rerunning these checks | **Pending** |
| Independent reproduction | No clean-checkout report tied to the final tree | **Pending / unverified** |

## 4. Competitive landscape at cutoff

### 4.1 Comparator selection

The primary head-to-head set is LangGraph/LangSmith, CrewAI, Microsoft AutoGen/Semantic Kernel and its Agent Framework successor, Dify, and Temporal. It spans low-level agent runtime, multi-agent framework, enterprise SDK, low-code platform, and durable execution engine. OpenAI Agents SDK, Google ADK/Vertex Agent Engine, PydanticAI, Mastra, and Haystack are included as relevant challengers. Commercial control planes are treated separately because managed operations and private service internals are not directly comparable to this repository.

### 4.2 Dated open-source inventory

Metrics below are direct GitHub REST API observations retrieved **2026-07-18 04:36–04:38 UTC**. Stars are adoption signals, not technical scores. `open_issues_count` includes pull requests under GitHub's repository API semantics.

| Product | Repository | Stars | Forks | Latest release observed | Release date (UTC) | Position/capabilities supported by primary sources |
|---|---|---:|---:|---|---|---|
| AgentGraph | https://github.com/gchahal1982/agentgraph | 0 | 0 | No release queried; **unverified** | — | Small vertical-first runtime assessed here |
| LangGraph | https://github.com/langchain-ai/langgraph | 37,528 | 6,290 | `1.2.9` | 2026-07-10 | Stateful graph runtime, persistence, durable execution, interrupts/HITL, memory, streaming; LangSmith adds deployment/tracing/evaluation: https://docs.langchain.com/oss/python/langgraph/overview and https://docs.langchain.com/langsmith/deployment |
| CrewAI | https://github.com/crewAIInc/crewAI | 55,711 | 7,864 | `1.15.4` | 2026-07-17 | Crews and event-driven Flows; persisted flow state is documented: https://docs.crewai.com/en/concepts/flows and https://docs.crewai.com/en/guides/flows/mastering-flow-state |
| AutoGen | https://github.com/microsoft/autogen | 59,800 | 8,997 | `python-v0.7.5` | 2025-09-30 | AgentChat/Core/Studio, teams, state save/load/pause/resume, experimental GraphFlow: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/index.html |
| Semantic Kernel | https://github.com/microsoft/semantic-kernel | 28,325 | 4,681 | `python-1.44.0` | 2026-07-07 | Multi-agent orchestration patterns and enterprise SDK surface; Microsoft Agent Framework is the successor path: https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/ and https://learn.microsoft.com/en-us/agent-framework/overview/ |
| Dify | https://github.com/langgenius/dify | 149,185 | 23,506 | `1.16.0` | 2026-07-17 | Production-oriented visual agent/workflow platform, agent nodes, plugins, APIs, self-hosting: https://docs.dify.ai/en/guides/workflow/node/agent and https://github.com/langgenius/dify |
| Temporal | https://github.com/temporalio/temporal | 21,706 | 1,742 | `v1.31.2` | 2026-07-08 | General durable execution, event history, activities/retries, timers, schedules, visibility, workers: https://docs.temporal.io/workflows and https://docs.temporal.io/encyclopedia/retry-policies |
| OpenAI Agents SDK | https://github.com/openai/openai-agents-python | 27,984 | 4,346 | `v0.18.3` | 2026-07-17 | Agents, handoffs, guardrails, sessions, tracing, MCP; standalone durable workflow semantics are **unverified**: https://openai.github.io/openai-agents-python/ |
| Google ADK | https://github.com/google/adk-python | 20,645 | 3,708 | `v2.5.0` | 2026-07-16 | Code-first agents, multi-agent composition, sessions/memory, evaluation, deployment path: https://google.github.io/adk-docs/ and https://cloud.google.com/products/gemini-enterprise-agent-platform |
| PydanticAI | https://github.com/pydantic/pydantic-ai | 18,627 | 2,381 | `v2.13.0` | 2026-07-18 | Type-safe agents/graphs, evals, MCP, durable-engine integrations: https://ai.pydantic.dev/ and https://pydantic.dev/docs/ai/integrations/durable_execution/overview/ |
| Mastra | https://github.com/mastra-ai/mastra | 26,303 | 2,458 | `@mastra/core@1.51.0` | 2026-07-15 | TypeScript agent/application framework; detailed cutoff capability verification beyond repository metadata is **unverified**: https://mastra.ai/docs |
| Haystack | https://github.com/deepset-ai/haystack | 25,928 | 2,930 | `v2.31.0` | 2026-07-08 | Pipeline/agent orchestration, components, evaluation ecosystem: https://docs.haystack.deepset.ai/docs/intro |

LangChain is broader than LangGraph: it supplies agent abstractions and integrations while LangGraph supplies the lower-level stateful runtime. LangSmith is the commercial observability/evaluation/deployment control plane. Official overview: https://docs.langchain.com/oss/python/langchain/overview and https://docs.langchain.com/oss/python/langgraph/overview.

### 4.3 Relevant commercial orchestration/control-plane products

| Product | Category role | Publicly documented capabilities relevant to SOTA | Evidence boundary |
|---|---|---|---|
| LangSmith Deployment | Managed/hybrid agent deployment and observability | Deployment, assistants/threads/runs, scaling, durable execution, tracing/evaluation; https://docs.langchain.com/langsmith/deployment | SLA, internal architecture, and comparative performance not tested; **unverified** |
| CrewAI Enterprise | Managed CrewAI control plane | Enterprise deployment/monitoring and governance are marketed at https://www.crewai.com/ | Exact cutoff entitlements, isolation, and performance are **unverified** |
| Microsoft Foundry Agent Service | Managed enterprise agent platform | Hosted agents, tools, identity/security integration, tracing/evaluation under Azure; https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview | Service behavior and regional feature parity not tested; **unverified** |
| Vertex AI Agent Engine | Managed runtime/control plane for agents | Deploy/manage agents, sessions and memory integrations, observability/evaluation paths; https://cloud.google.com/products/gemini-enterprise-agent-platform | Service guarantees and framework parity not tested; **unverified** |
| Amazon Bedrock Agents | Managed agent service | Foundation-model orchestration, action groups, knowledge bases, traces, multi-agent collaboration; https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html | Durable workflow/HITL equivalence to dedicated engines is **unverified** |
| Temporal Cloud | Managed durable execution | Hosted Temporal service, visibility, schedules, operational controls; https://temporal.io/cloud | Agent-specific authoring remains application/framework responsibility |
| Salesforce Agentforce | SaaS agent platform | CRM-native agent authoring/actions/governance; https://www.salesforce.com/agentforce/ | General-purpose runtime portability and comparative semantics are **unverified** |
| IBM watsonx Orchestrate | Enterprise agent/work orchestration | Agent/tool catalog and business orchestration; https://www.ibm.com/products/watsonx-orchestrate | Detailed execution guarantees and matched performance are **unverified** |

## 5. Weighted criteria

Weights were chosen before assigning ratings for this dossier and sum to 100. Critical criteria emphasize correctness and control over feature count. Ratings use 0–4 anchors and count only current repository evidence. Weighted points are `weight × rating / 4`.

| Criterion | Weight | SOTA target | AgentGraph rating | Weighted points | Reason |
|---|---:|---|---:|---:|---|
| Durable execution and recovery | 20 | Crash-safe replay/recovery, retries, timers, cancellation, idempotency, distributed concurrency, migration/fault proof | 2 | 10.0 | Functional per-node SQLite checkpoints and resume; production semantics/failure evidence missing |
| Orchestration expressiveness | 15 | Typed state, cycles, branches, fan-out/join, subgraphs, streaming, multi-agent patterns, budgets | 2 | 7.5 | Sequential graph and agent/tool loop work; advanced composition absent |
| Human control | 10 | Persisted interrupts, authenticated approvals, edit/reject/escalate/timeout/resume | 1 | 2.5 | Interfaces and graph convention only |
| Security, governance, audit | 15 | External identity, scoped policy, tenant isolation, complete immutable audit, secrets/redaction, security proof | 1 | 3.75 | Node RBAC/basic bearer/partial audit; material authorization and audit defects |
| Observability and evaluation | 15 | OTel traces/metrics/logs, model/tool spans, datasets/evals, replay, quality/cost gates | 1 | 3.75 | Custom node spans and counters only |
| Interoperability/ecosystem | 10 | Broad model/tool/data ecosystem, MCP/A2A, extension conformance, provider tests | 1 | 2.5 | Three provider paths and protocols; no open agent/tool protocols |
| Deployment and operations | 10 | Workers/queues/schedules, autoscaling, migrations, rollback, SLO/load/chaos evidence, secure images | 1 | 2.5 | Docker/Compose and basic health only |
| Developer/product differentiation | 5 | Excellent SDK/docs/studio plus validated differentiated workflows/adoption | 2 | 2.5 | Clean small API and seven packs; dashboard/integrations/adoption immature |
| **Diagnostic total** | **100** | — | — | **35.0 / 100** | Progress indicator only; hard-gate failures control verdict |

Sensitivity does not affect the verdict: even doubling the 5-point differentiation criterion cannot repair any critical gate, and removing any single criterion leaves multiple hard failures.

## 6. Head-to-head assessment

Legend: **D** demonstrated by code/test or authoritative operational evidence; **P** partial/prototype; **O** stated in current official documentation but not independently tested here; **—** no qualifying evidence found in the selected source set; **U** unverified. Competitor cells describe public capability evidence, not implementation-quality certification.

| Critical dimension | AgentGraph | LangGraph + LangSmith | CrewAI | Microsoft Agent Framework / AutoGen / SK | Dify | Temporal | AgentGraph outcome |
|---|---|---|---|---|---|---|---|
| Stateful graph/workflow composition | D | O | O | O | O | O | Non-inferiority **unverified**; narrower than several peers |
| Durable persistence/resume | P | O | O | P/O | O | O | **Fail** on semantics and evidence depth |
| Retries/timers/schedules/cancellation | — | P/O | P/O | P/O | P/O | O | **Fail** |
| Distributed workers/concurrency control | — | O via deployment | O via enterprise, details U | O via managed service, details U | O | O | **Fail** |
| Human interrupt/approval/resume | P interface only | O | O/P | O | O/P | Application-defined atop workflows | **Fail** |
| Complete traces/evals/replay tooling | P | O | O | O | O | O for workflow visibility, agent eval application-defined | **Fail** |
| Identity/tenant enterprise controls | P and unsafe role assertion | O via control plane | O, details U | O via Azure | O, details U | O via Cloud/self-host controls | **Fail** |
| Open interoperability | Three provider adapters | Large LangChain ecosystem | Tools/integrations | Azure/plugin ecosystem | Plugin marketplace | Language SDKs/Nexus | **Fail**; MCP/A2A absent |
| Visual authoring/operations | Minimal dashboard | LangSmith Studio/control plane O | Enterprise UI O | AutoGen Studio/Foundry O | Core strength O | Web UI O | **Fail** |
| Domain-ready vertical packs | D: seven templates | — in core | — in core | — in core | Templates/marketplace O | — | Potential **lead**, but production outcome superiority is U |
| Reproducible comparative evidence | — | Not measured here | Not measured here | Not measured here | Not measured here | Not measured here | **Inconclusive**, therefore cannot pass SOTA gate |

Temporal is complementary as well as competitive: pairing an agent SDK with Temporal can deliver execution guarantees AgentGraph currently lacks. PydanticAI explicitly documents durable-engine integrations, making “small typed agent API plus proven durable substrate” an important architectural alternative.

## 7. Exhaustive feature matrix

This matrix is exhaustive against the frozen category taxonomy in §1 for the selected technical comparators; it is not a claim that every private or newly released feature worldwide was discovered. `O` means the linked official source documents the capability, not that this assessment independently reproduced it.

Abbreviations: **AG** AgentGraph; **LG** LangGraph/LangSmith; **CR** CrewAI; **MS** Microsoft AutoGen/Semantic Kernel/Agent Framework; **DF** Dify; **TP** Temporal; **OA** OpenAI Agents SDK; **ADK** Google ADK/Agent Engine; **PAI** PydanticAI.

| Feature | AG | LG | CR | MS | DF | TP | OA | ADK | PAI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Directed graph/workflow API | D | O | O | O | O | O | P | O | O |
| Conditional routing/cycles | D | O | O | O | O | O | O via agent loop | O | O |
| Typed state/schema | D | O | O | O | O | O via SDK languages | O/P | O | O |
| Multi-agent delegation/handoff | P | O | O | O | O | App-defined | O | O | O |
| Parallel fan-out/join | — | O | O | O | O | O | O/P | O | P/O |
| Subgraphs/composable workflows | — | O | O/P | O | O | O child workflows | P | O | O |
| Streaming run events | — | O | O | O | O | O visibility/event APIs | O | O | O |
| Structured model output validation | P | O via ecosystem | O | O | O | App-defined | O | O | O |
| Tool JSON-schema generation | D | O | O | O | O | App-defined | O | O | O |
| Tool execution sandbox | — | Deployment-dependent U | Enterprise-dependent U | Managed-dependent U | Plugin sandbox details U | Activity isolation app-defined | Hosted tools dependent U | Managed-dependent U | —/U |
| Per-node durable checkpoint | D | O | O flow persistence | P/O | O | O event history | Session persistence, durability U | O/P | O/integrations |
| Cross-process resume | P | O | O | P/O | O | O | Session resume P; durable semantics U | O | O |
| Deterministic replay | — | O/P | —/U | —/U | —/U | O | — | —/U | Via durable engine O |
| Automatic activity/tool retry | — | O/P | O/P | O/P | O/P | O | —/P | O/P | Via durable engine O |
| Durable timers/schedules | — | Deployment O/P | —/U | Managed O/P | Scheduled triggers O/P | O | — | Managed O/P | Via durable engine O |
| Cancellation/termination API | — | O | O/P | O | O | O | O/P | O/P | Engine-dependent O/P |
| Idempotency key/side-effect contract | — | P/O | —/U | —/U | —/U | O patterns | — | —/U | Engine-dependent O |
| Worker leases/fencing/backpressure | — | Deployment O | Enterprise U | Managed U | O/U | O | — | Managed U | Engine-dependent O |
| Persisted human interrupt | — | O | O/P | O | O/P | App-defined O | Handoff only P | O/P | O/P |
| Approval inbox/reviewer workflow | — | LangSmith O | Enterprise U | Foundry O/U | O/P | App-defined | — | Managed U | —/U |
| Human edit/reject/resume | — | O | O/P | O | O/P | App-defined | P | O/P | O/P |
| Short-term session memory | D state/messages | O | O | O | O | App-defined | O | O | O |
| Durable long-term semantic memory | P interface | O | O | O | O | App-defined | O/P | O | O |
| OpenAI-compatible models | D | O | O | O | O | App-defined | OpenAI native | O via integrations | O |
| Anthropic direct adapter | D | O | O | O | O | App-defined | —/U | O | O |
| Local Ollama adapter | D | O | O | O/P | O | App-defined | —/U | O/P | O |
| Broad provider registry/routing | P | O | O | O | O | App-defined | P | O | O |
| MCP support | — | O | O | O | O | App-defined | O | O | O |
| A2A support | — | Ecosystem O/P | —/U | O/P | —/U | Nexus/general interoperability O/P | —/U | O | —/U |
| Built-in tracing | P node only | O | O | O | O | O workflow visibility | O | O | O |
| OpenTelemetry export | — | O | O/P | O | O/P | O | O/P | O | O via Logfire/integrations |
| Model/tool span detail | — | O | O | O | O | App instrumentation | O | O | O |
| Cost/token accounting | D counters | O | O | O | O | App-defined | O | O | O |
| Evaluation datasets/runners | — | O | O/P | O | O | App-defined | —/P | O | O |
| CI quality regression gates | — | O via LangSmith | Enterprise U | O/P | U | App-defined | App-defined | O | O |
| Run replay/debug studio | — | O | O | AutoGen Studio O | O | Web UI O | Trace UI O | Dev UI O | Logfire O |
| Runtime audit log | P incomplete | Control-plane O | Enterprise U | Foundry O/U | O/U | Event history O | Tracing, audit semantics U | Managed U | App/integration-defined |
| Node/tool RBAC | P node only | Control-plane O; runtime app-defined | Enterprise U | Azure identity/policy O | O/U | Namespace/auth O; app policy | App-defined | Cloud IAM O; app policy | App-defined |
| External identity binding | — | Control-plane O | Enterprise U | Azure O | Enterprise U | O | Hosted platform-dependent | Cloud IAM O | App-defined |
| Tenant isolation | — | Control-plane O | Enterprise U | Azure O | Enterprise U | Namespace O | Hosted platform-dependent U | Cloud O | App-defined |
| Secret manager integration | — | Deployment O/P | Enterprise U | Azure O | O/P | Deployment-defined | Hosted/platform-defined | Cloud O | App-defined |
| PII/secret redaction controls | — | O | O/P | O | O/P | App-defined | O/P | O/P | O |
| Rate limits/quotas/budgets | — | O/P | O/P | Managed O | O | App-defined | Hosted API O | Managed O | App-defined |
| REST service API | D | O | Enterprise O | Managed/Studio O | O | O service APIs | Library; hosted API context | Managed O | Library/app-defined |
| Run status/cancel/resume API | — | O | Enterprise U | O | O | O | P | O | App-defined |
| Webhooks/event subscriptions | — | O | Enterprise U | O/P | O | O/P | —/U | O/P | App-defined |
| Self-host deployment | D compose | O options | O | Framework yes; managed service no | O | O | O library | O library | O library |
| Managed cloud control plane | — | O | O | O | O | O | OpenAI platform context O | O | Logfire/integrations O |
| Kubernetes/Helm artifacts | — | O | U | Azure managed | O/P | O | — | Cloud managed | —/U |
| Schema/data migrations | — | O/U | U | Managed U | O | O | — | Managed U | Engine-dependent |
| Load/fault/chaos evidence in repo | — | U in this assessment | U | U | U | U | U | U | U |
| Visual authoring | — | Studio O | O | AutoGen Studio/Foundry O | O | — | — | Dev UI P/O | — |
| Seven packaged business verticals | D templates | — | — | — | Marketplace/templates O | — | — | Samples O | — |
| Production connector implementations | — | Large ecosystem O | O | O | Marketplace O | Generic activities | MCP/tools O | O | O |
| Public adoption at cutoff | 0 stars | 37,528 | 55,711 | 59,800 AutoGen / 28,325 SK | 149,185 | 21,706 | 27,984 | 20,645 | 18,627 |

## 8. Standardized gap table

| Dimension | Current State | SOTA Target | Gap | Effort (S/M/L/XL) | Priority (P0-P3) |
|---|---|---|---|---|---|
| Identity and authorization | Shared bearer token; request body self-asserts `principal_roles`; auth can run open | OIDC/JWT or workload identity mapped server-side to tenant/resource-scoped policy; deny-by-default | Privilege escalation and no identity provenance | L | P0 |
| Tool policy enforcement | `requires_principal` metadata is not enforced by tool execution | Central pre/post tool policy with permission, tenant, approval, network, and data classification checks | Claimed tool-layer RBAC is bypassable | M | P0 |
| Audit completeness | Run start/end, errors, allow decisions; model/tool/handoff/retry event enums mostly unused | Complete correlated lifecycle records, deny events, redaction, append-only integrity, export and retention | Core governance claim contradicted | L | P0 |
| Human approval | Handoff interfaces and `__goto__`; no durable lifecycle/API | Persisted interrupt/approval entity, authenticated reviewer actions, timeout/escalation, edit/reject/resume | No real HITL control plane | XL | P0 |
| Durable correctness | Per-node checkpoint after side effects; direct latest-thread resume | Transactional/outbox side-effect protocol, idempotency, leases/fencing, retries, cancellation, replay/version migrations, fault tests | Recovery can duplicate effects or race; semantics unspecified | XL | P0 |
| Reproducible release gate | Local dev pins added; session-reported tests; lint/SOTA pending; mypy non-blocking | Fully pinned clean CI, all tests/lint/types/security/SOTA, artifacts, coverage, SBOM/signing/provenance | Release cannot be independently certified | M | P0 |
| API run lifecycle | Synchronous run only; no get/cancel/resume/approve/stream; detailed exceptions exposed | Versioned asynchronous run API with idempotency, status, cancel, resume, SSE/WebSocket, webhooks, stable errors | Not operable for long-running agents | L | P1 |
| Distributed execution | No queue/workers/backpressure/leases | Horizontally scalable workers, admission control, fairness, retries/DLQ, autoscaling, ownership fencing | Postgres storage alone is not multi-node orchestration | XL | P1 |
| Observability | Custom node spans to structlog | OpenTelemetry model/tool/node/run spans, metrics/log correlation, exporters, dashboards, redaction, sampling | No production telemetry plane | L | P1 |
| Evaluation | No agent quality/safety datasets or runner | Offline/online evals, trajectory assertions, golden datasets per vertical, LLM-judge calibration, CI thresholds | No proof verticals produce good/safe outcomes | XL | P1 |
| Interoperability | OpenAI-compatible, Anthropic, Ollama adapters | MCP client/server, A2A where relevant, broader provider conformance, connector SDK | Ecosystem and portability lag | L | P1 |
| Postgres proof | Implemented adapters; no retained live integration/failover evidence | Ephemeral Postgres CI, migrations, contention/restart/failover tests, backup/restore | Multi-node/durability claims unproven | L | P1 |
| Memory | In-memory substring implementation; not runtime-integrated | Durable tenant-scoped semantic/episodic memory, provenance, deletion, retention, evals | Interface only | L | P2 |
| UI/control plane | Minimal pages; threads endpoint mismatch; no handoff/trace/eval UX | Authenticated run/trace/approval/eval/graph operations console | Operational UX incomplete | L | P2 |
| Vertical connectors | Protocols plus in-memory demo stores | Supported CRM/ticketing/EHR/ATS/GRC/project connectors with contract/sandbox tests | “Business outcomes” stop at templates | XL | P2 |
| Vertical safety/compliance | Role names and prompts; compliance readiness claims unverified | Threat models, PHI/PII controls, clinical/financial safety policies, independent assessments and certifications as applicable | Regulated deployment evidence absent | XL | P1 |
| Deployment hardening | Root containers, floating `pip install uv`, no K8s/migrations | Non-root digest-pinned images, secret injection, migrations, Helm/operator, probes, rollback, SLOs | Prototype deployment posture | L | P1 |
| Performance/scalability | No benchmarks | Frozen workload suite, latency/throughput/cost/resource baselines, soak/load/chaos tests vs top set | No comparative operating evidence | XL | P1 |
| Documentation accuracy | Strong claims exceed code | Claim-to-test links, limitations, deployment threat model, supported guarantees | Trust and compliance risk | M | P0 |
| Community/release maturity | New repo, 0 stars/forks, no security/governance/changelog evidence | Versioned releases, support/security policy, governance, downstream references and adopters | Adoption/maintenance durability unproven | L | P2 |
| SOTA evidence roots | Schemas/framework only; product evidence absent | Frozen scope/criteria/competitors/sources/claims/gaps/runs/verdict and independent adjudication | No machine-verifiable dossier basis | L | P1 |

## 9. P0 implementation path

P0 is the minimum trustworthy-runtime program. It should be completed before adding more verticals.

### P0.1 Establish a reproducible baseline

1. Finish the current remediation and run a clean checkout at the exact SHA with `uv sync --frozen --all-packages --all-extras` (or the project's final canonical equivalent).
2. Make lint, formatting check, typecheck, root test suite, UI build/typecheck, SOTA verifier/render check, dependency audit, and secret scan blocking. Remove `mypy ... || true`.
3. Pin CI actions and uv/Python versions; produce JUnit, coverage, environment manifest, lock hash, tested SHA, and logs as retained artifacts.
4. Add SBOM, artifact signing/provenance, release notes, upgrade notes, `SECURITY.md`, and supported-version policy.
5. Convert the reported 81-test result from ephemeral session context into a retained report. Until then, preserve the wording “session-reported; independent reproduction unverified.”

**Exit evidence:** clean Linux Python 3.11/3.12 runs, UI build, all gates green twice, artifacts downloadable and hash-bound to the tested SHA.

### P0.2 Repair identity and policy boundaries

1. Remove `principal_roles` as an authority source from `RunBody`. Resolve principal and tenant from validated OIDC/JWT claims or a trusted reverse-proxy/workload identity.
2. Introduce resource-scoped policy input: tenant, environment, graph, tool, data class, action, and attributes. Default deny unknown roles/permissions.
3. Enforce policy in one unavoidable tool dispatcher before invocation, including `requires_principal`; add post-call output policy/redaction.
4. Audit allows **and denies** without logging secrets/PHI. Return stable 401/403 errors and stop exposing internal exception strings.
5. Make unauthenticated mode an explicit development flag that cannot bind a non-loopback host.
6. Add cross-tenant, forged-role, missing-claim, confused-deputy, tool-bypass, and audit-redaction security tests.

**Exit evidence:** threat model, negative integration suite, tenant leakage tests, policy decision records, and independent security review.

### P0.3 Make audit claims true

1. Define a stable event schema with run/trace/span/node/model/tool/policy/handoff IDs, attempt, tenant, actor identity, timestamps, input/output digests, token/cost, status, and redaction metadata.
2. Emit model-call start/end/error and tool-call start/end/error around the actual dispatcher, plus denied policy, retry, interrupt, approval, resume, cancel, and run terminal events.
3. Use transactional outbox or equivalent coupling where state and audit must agree. Remove replacement semantics for immutable records.
4. Add append-only integrity (hash chain/signature or external immutable sink), retention/export, pagination, and access policy.
5. Validate event completeness with trajectory tests and failure injection.

**Exit evidence:** every canonical and failure trajectory reconciles expected/actual events; tamper and redaction tests pass.

### P0.4 Implement real human-in-the-loop

1. Add a persisted `Interrupt`/`Approval` state machine (`pending`, `claimed`, `approved`, `edited`, `rejected`, `expired`, `cancelled`) with optimistic concurrency/version.
2. Make a node return an interrupt command that checkpoints **before** stopping execution. Do not use an ordinary `goto` as a substitute.
3. Add authenticated list/claim/resolve endpoints; bind reviewer permissions and tenant; include expected checkpoint/version to prevent stale approval.
4. Resume with a typed reviewer payload, preserving run identity and creating a new attempt/span; support rejection route, edit validation, timeout/escalation, cancellation, and webhook/SSE notification.
5. Add restart, duplicate approval, concurrent reviewer, stale token, timeout, denial, and cross-tenant tests.

**Exit evidence:** process-kill/restart approval scenario succeeds exactly once with complete audit and no unauthorized resolution.

### P0.5 Specify and prove durable execution semantics

1. Publish guarantees per operation: what is at-most-once, at-least-once, or effectively-once; require idempotency keys for side-effecting tools.
2. Persist run/node-attempt lifecycle before execution; add worker leases, heartbeat, fencing token, retry policy, timeout, cancellation, and terminal states.
3. Couple checkpoint/outbox updates transactionally. Provide compensations or explicit non-retryable operations for external side effects.
4. Version graph/state/tool schemas and implement migration/replay compatibility rules.
5. Add fault injection at every boundary: before/after model call, tool side effect, audit write, checkpoint commit, worker death, DB reconnect, and approval resolution.
6. Consider building on Temporal/DBOS/Restate rather than reproducing a distributed workflow engine. Preserve AgentGraph's vertical/runtime API above the substrate.

**Exit evidence:** deterministic failure matrix, contention tests, process/DB restart tests, no duplicate externally observed effects under the declared protocol, and a published guarantees document.

### P0.6 Correct public claims

Until exit evidence exists, change product language to “checkpointed graph prototype,” “partial audit,” “node-level RBAC,” and “handoff interfaces.” Remove or explicitly mark multi-tenant, HIPAA/SOC2-ready, complete audit, OTel, and production durability statements as **unverified**. Documentation accuracy is a safety feature, not marketing cleanup.

## 10. P1 implementation path

### P1.1 Production run service

Build a versioned asynchronous API with create/get/list/cancel/resume/approve endpoints, idempotency keys, pagination, SSE/WebSocket event stream, signed webhooks, stable error taxonomy, request limits, and generated clients. Separate API admission from workers and introduce queue/backpressure, priorities, quotas, fairness, DLQ/re-drive, and autoscaling.

### P1.2 Observability and evaluation plane

Instrument OpenTelemetry run/node/model/tool/policy/handoff spans and metrics; ship collector configuration and dashboards. Add redaction and sampling. Create frozen datasets for every vertical with deterministic tool-trajectory assertions, expected routing, safety/policy cases, quality rubrics, cost/latency budgets, and calibrated model judges. Gate regressions in CI and support production feedback-to-dataset workflows.

### P1.3 Interoperability

Implement MCP client and server adapters with auth, capability negotiation, timeouts, policy wrapping, and conformance tests. Evaluate A2A for cross-agent interoperability. Add provider contract suites for streaming, tools, structured output, errors, usage, cancellation, and rate limits. Add model routing/fallback only after deterministic semantics and budget policies exist.

### P1.4 Postgres and deployment hardening

Create schema migrations and supported upgrade paths. Run ephemeral Postgres integration tests plus lock/contention/failover/backup-restore scenarios. Publish non-root, digest-pinned images with health/readiness/startup probes and secret-manager integration. Add Helm/Kubernetes only with rolling-upgrade, migration, rollback, resource-limit, network-policy, and disruption tests.

### P1.5 Safety and regulated vertical evidence

For each regulated workflow, map data classes, purpose, actor, policy, retention, redaction, and human authority. Add domain expert review and adversarial datasets. Never infer HIPAA/SOC2 readiness from an audit table and roles; obtain independent control evidence and contractual/compliance artifacts where applicable. Clinical, legal, financial, and insurance outcome claims remain **unverified** until domain validation exists.

### P1.6 Matched SOTA evidence

Populate the repository's product evidence roots. Freeze comparator versions/images and test protocols. Run matched workloads for recovery correctness, approval safety, throughput/latency/cost, trace completeness, developer task completion, and vertical outcome quality. Select top comparators only after measurements, apply non-inferiority deltas and confidence intervals, and obtain independent adjudication.

## 11. Validation evidence and missing proof

### 11.1 Evidence present

- Unit/integration-style tests exercise graph completion, conditional routes, checkpoints, policy allow/reject behavior, tool schema/execution, provider mocks, SQLite persistence, API auth/health/run, SDK, vertical happy paths, and SOTA schema/scoring logic.
- The FastAPI end-to-end test starts registered verticals with an explicit test provider and runs `qualify_lead` through HTTP.
- SQLite and in-memory persistence are exercised; Postgres code exists.
- SOTA schema tests cover deterministic scoring/verdict behavior and offline contract validation.
- The current session reports 81 passing tests before lint after remediation; retained proof is **unverified**.

### 11.2 Evidence absent or pending

- Full final-tree lint and SOTA verification: **pending** with main agent.
- Clean environment reproduction tied to a final SHA: absent.
- Postgres live integration, restart, contention, failover, migration, backup/restore: absent.
- Crash/fault injection, retries, cancellation, idempotent side effects, worker concurrency: absent.
- Handoff/approval runtime/API tests: absent.
- Model/tool audit completeness and deny audit tests: absent.
- External identity, tenant isolation, security/adversarial tests: absent.
- Live provider conformance, streaming, fallback, rate-limit behavior: absent.
- OTel exporter/collector/dashboard verification: absent.
- Quality/safety eval datasets and real connector sandboxes: absent.
- Load, soak, chaos, cost, and matched competitor benchmarks: absent.
- Independent user/adopter, compliance, or security validation: absent.

## 12. Roadmap and measurable exit criteria

| Horizon | Deliverable | Measurable exit criteria |
|---|---|---|
| 0–30 days | Trustworthy baseline and claim correction | Clean pinned CI; all checks blocking; retained artifacts; unsafe role assertion removed; `requires_principal` enforced; complete model/tool/deny audit; public claims reconciled |
| 31–90 days | Durable run/approval MVP | Persisted run attempts, leases/fencing, retries/timeouts/cancel, idempotency protocol, approval state machine/API, process-kill and duplicate-resolution tests |
| 91–180 days | Operable platform | Async workers/queue/backpressure, OTel stack, eval runner/datasets, Postgres failure suite/migrations, secure images, run stream/webhooks, MCP |
| 181–270 days | Vertical production proof | At least two real connector sandboxes, domain-reviewed safety suites, tenant isolation review, load/soak/chaos reports, upgrade/rollback drills |
| 271–365 days | Comparative adjudication | Frozen top set, matched benchmark artifacts, non-inferiority on every critical dimension, independent reproduction/review, no open P0/P1 blockers |

A plausible product strategy is **not** to out-feature every general framework. AgentGraph can lead as a vertical-first governed runtime if it combines: (a) proven durable substrate, (b) identity-bound policy/audit, (c) approval-centric operations, and (d) validated domain packs. The present code demonstrates the API shape for that strategy, not its completion.

## 13. Evidence provenance and staleness

### 13.1 Repository provenance

Repository facts are from direct inspection of the local assessed tree and working diff on 2026-07-18. The base SHA and branch are recorded at the top. Because other agents may continue remediation, line numbers and working-tree status can become stale immediately; claims should be rechecked against the final SHA. No files other than this dossier were changed by this assessment.

### 13.2 External provenance

Primary sources were preferred:

- GitHub REST repository and release APIs, retrieved 2026-07-18, for dated metrics/releases.
- Official repositories and official product documentation for capability claims.
- Commercial marketing pages only for public positioning; private internals, SLAs, exact entitlements, scale, security posture, and comparative performance remain **unverified** unless explicitly documented and independently tested.

Core source URLs:

- AgentGraph repository: https://github.com/gchahal1982/agentgraph
- LangChain overview: https://docs.langchain.com/oss/python/langchain/overview
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangSmith Deployment: https://docs.langchain.com/langsmith/deployment
- CrewAI Flows: https://docs.crewai.com/en/concepts/flows
- CrewAI flow state: https://docs.crewai.com/en/guides/flows/mastering-flow-state
- AutoGen AgentChat: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/index.html
- AutoGen state: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html
- AutoGen GraphFlow: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/graph-flow.html
- Semantic Kernel orchestration: https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/
- Microsoft Agent Framework: https://learn.microsoft.com/en-us/agent-framework/overview/
- Dify repository: https://github.com/langgenius/dify
- Dify Agent node: https://docs.dify.ai/en/guides/workflow/node/agent
- Temporal workflows: https://docs.temporal.io/workflows
- Temporal retry policies: https://docs.temporal.io/encyclopedia/retry-policies
- Temporal schedules: https://docs.temporal.io/schedule
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- OpenAI handoffs: https://openai.github.io/openai-agents-python/handoffs/
- OpenAI guardrails: https://openai.github.io/openai-agents-python/guardrails/
- Google ADK: https://google.github.io/adk-docs/
- Vertex AI Agent Engine: https://cloud.google.com/products/gemini-enterprise-agent-platform
- PydanticAI: https://ai.pydantic.dev/
- PydanticAI durable execution: https://pydantic.dev/docs/ai/integrations/durable_execution/overview/
- Mastra: https://mastra.ai/docs
- Haystack: https://docs.haystack.deepset.ai/docs/intro
- Amazon Bedrock Agents: https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html
- Azure Foundry Agent Service: https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview
- Temporal Cloud: https://temporal.io/cloud
- Salesforce Agentforce: https://www.salesforce.com/agentforce/
- IBM watsonx Orchestrate: https://www.ibm.com/products/watsonx-orchestrate

### 13.3 Staleness policy

- GitHub counts and “latest release” facts are snapshots and stale after 2026-07-18 04:38 UTC.
- Fast-moving framework capabilities should be refreshed after 30 days or before any investment/procurement claim.
- Commercial plans, regions, pricing, security attestations, and preview/GA status should be refreshed immediately before use.
- Repository capability findings must be rerun after remediation lands; passing unit tests do not automatically update any finding about semantics, security, or production proof.
- An unreachable or moved URL does not negate a historical observation but lowers current verifiability; mark the affected claim **unverified** until refreshed.

## 14. Defensible verdict

**Not Yet SOTA.**

AgentGraph has a promising differentiator—seven domain-oriented packs over one small typed runtime—and demonstrable happy-path foundations. It does not meet the category's critical evidence gates. The most serious blockers are not missing polish: they are unsafe identity/role binding, unenforced tool metadata, incomplete audit, non-integrated human approval, unspecified distributed/durable side-effect semantics, and absent matched frontier evidence. The current remediation improves build reproducibility and fixes a FastAPI schema defect plus malformed exception handling, but full lint/SOTA verification remains pending and cannot convert these architectural gaps into passes.

The verdict can change only after the P0/P1 exit evidence is retained and independently reproducible. A high weighted feature score, more vertical templates, or popularity growth would not by itself qualify. SOTA requires AgentGraph to demonstrate non-inferiority or leadership on every critical dimension against the frozen top comparator set with all hard gates passing. That evidence does not exist today.
