# AgentGraph architecture

This document explains the design decisions behind AgentGraph and how
the pieces fit together.

## The runtime is the product

Frameworks ship primitives and let users compose them. AgentGraph ships
the runtime, audit log, RBAC, observability, and checkpointing
**together** because every production agent needs all four. Building
them into one runtime means vertical packs inherit them for free.

```
                 ┌──────────────────────────────────────────┐
                 │             Vertical pack                │
                 │  (sales-ops, support-ops, compliance...) │
                 │                                          │
                 │  agents  ─►  tools  ─►  prompts          │
                 │     │                                  │
                 │     ▼                                  │
                 │  graph (compiled)                      │
                 └────────────┬─────────────────────────────┘
                              │
                              ▼
                 ┌──────────────────────────────────────────┐
                 │           agentgraph-runtime             │
                 │                                          │
                 │  • Walk graph                           │
                 │  • Enforce policy on each node          │
                 │  • Checkpoint after each node           │
                 │  • Emit audit events                    │
                 │  • Open OTel spans                      │
                 │  • Pause / resume via handoff            │
                 └────────────┬─────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        core (primitives)   llm (providers)   server (FastAPI)
```

## Graph execution

A graph is a DAG (or near-DAG with conditional cycles) of `Node`s
connected by `Edge`s. Nodes are async callables that take a
`GraphState` and return a `NodeResult`. The runtime:

1. Looks up the current node in the graph.
2. Enforces any `requires` policy against the principal.
3. Runs the node inside an OTel span.
4. Writes an audit event (`tool.call` or `model.call`).
5. Determines the next node from `NodeResult.next`, `NodeResult.goto`,
   static edges, or conditional edges.
6. Snapshots the state to the `CheckpointStore`.
7. Loops until a node returns `end=True` or `current == END`.

## Checkpointing

After every node, the runtime snapshots the full `GraphState` to a
`CheckpointStore`. The default is in-memory; production deployments
swap in a Postgres-backed store. A checkpoint is keyed by `run_id`
and `thread_id`, so:

- A run can be paused and resumed across process restarts.
- The same `thread_id` can be replayed with different inputs.
- Failures in a long-running agent don't lose progress.

## RBAC

`Tool`s declare what they need via `requires_principal=True` and (via
the parent `Node`) `requires=<permission>`. The runtime checks the
principal against the role->permission mapping before invoking the
tool. Tools that touch PHI in healthcare, for example, are unreachable
without a `clinician` role.

Vertical packs ship their own role overrides via `with_role(...)`.

## Audit

Every privileged action emits an `AuditEvent` with `run_id`,
`thread_id`, `principal_id`, `action`, `actor`, and a payload. The
runtime writes to an `AuditLog` interface. Production deployments
should use a tamper-evident store (Postgres + WORM bucket, AWS QLDB).

## Handoff

A tool can return `ctx.state["__goto__"] = "human_handoff"` to signal
a transition out of the agent node. The runtime pauses the run,
emits a `Handoff` record, and (optionally) waits for a human reply
via a configured `HandoffChannel`. When the human replies, the run
resumes from its last checkpoint.

## LLM providers

`agentgraph-llm` is a thin provider abstraction. The runtime calls
`LLM.complete(messages, tools=...)` and gets back a `ModelResponse`.
Providers in the box: OpenAI, Anthropic, Ollama, and a `Mock` used in
tests. Adding a new provider is a `register_provider` call.

## Why uv workspaces?

We use [uv](https://github.com/astral-sh/uv) for workspaces because:
- It's fast (Rust resolver, parallel installs).
- It locks the entire workspace deterministically (`uv.lock`).
- Workspaces mirror the directory layout, so you can `cd` into a
  package and run `uv run` without juggling virtualenvs.

## Future work

- **Postgres checkpoint store** with row-level locking.
- **OpenTelemetry exporter** for spans and audit events.
- **Built-in vector memory** for long-term semantic recall.
- **WebSocket run stream** for live UI updates.
- **Multi-tenant isolation** via per-principal audit partitions.
- **AgentGraph Studio** (Next.js) for authoring graphs visually.
