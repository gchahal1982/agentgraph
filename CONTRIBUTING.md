# Contributing to AgentGraph

Thanks for your interest in AgentGraph. This document covers how to set
up a dev environment, the layout of the workspace, and how to add a new
vertical.

## Development setup

```bash
# Requires Python 3.11+, uv, and (optionally) node 22+ for the UI.
git clone https://github.com/anomalyco/agentgraph
cd agentgraph
uv sync --all-packages
uv run --all-packages python -m pytest tests -q
```

## Layout

```
agentgraph/
├── packages/
│   ├── core/      primitives (agents, tools, audit, RBAC, observability)
│   ├── llm/       provider abstraction (OpenAI, Anthropic, Ollama, Mock)
│   ├── runtime/   graph execution, checkpoints, handoff
│   ├── sdk/       Agent, Graph, Runner
│   ├── server/    FastAPI HTTP layer
│   └── cli/       `ag` command
├── verticals/
│   ├── _shared/   agentgraph-verticals (base scaffolding)
│   ├── sales-ops/
│   ├── support-ops/
│   ├── compliance/
│   ├── recruiting/
│   ├── insurance/
│   ├── construction/
│   └── healthcare/
├── tests/         unit tests for core, llm, runtime, sdk, server, verticals
├── examples/      runnable demos
├── docs/          architecture and guides
└── ui/            Next.js dashboard
```

## Adding a new vertical

1. Create `verticals/<name>/` with `pyproject.toml`, `README.md`, and
   `src/agentgraph_<name>/`.
2. Add it to the root `pyproject.toml`'s `[tool.uv.workspace]` members.
3. Implement:
   - `agents.py`     - the agent specs and prompts
   - `tools.py`      - domain tools with pluggable backends
   - `graphs.py`     - the compiled graph(s)
   - `policies.py`   - role -> permission overrides
   - `service.py`    - `Service.default()` and FastAPI app
4. Add tests in `tests/test_<name>.py`.
5. Document the outcomes in the package README.

## Coding conventions

- Python 3.11+, 4-space indent, max line length 100.
- Type hints everywhere; Pydantic models for external boundaries.
- Tools take `ToolContext` as their first parameter.
- Verticals depend only on the public APIs of `agentgraph-core`,
  `agentgraph-runtime`, `agentgraph-sdk`, and `agentgraph-llm`.

## Commit style

Use conventional commits:

```
feat(sales-ops): add CSV upload for bulk lead qualification
fix(runtime): handle unknown node names without raising
docs(readme): clarify the verticals table
```

## Code review

- New verticals must include at least one test that exercises the
  default service end-to-end.
- Tools must declare `requires_principal=True` if they touch PII / PHI.
- Audit-relevant actions (sign-off, evidence attachment) must produce
  an audit event. The runtime handles most of this automatically;
  tools that bypass the runtime must write events directly.

## License

By contributing, you agree that your contributions will be licensed
under the Apache 2.0 License. See [LICENSE](./LICENSE).
