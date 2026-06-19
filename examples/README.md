"""Runnable examples for AgentGraph.

Each subdirectory contains a runnable demo for one vertical. Run them
from the repo root with the project's `uv` environment, e.g.:

    uv run --all-packages python examples/sales_ops/qualify_lead.py
    uv run --all-packages python examples/support_ops/triage_ticket.py
    uv run --all-packages python examples/healthcare/triage_intake.py
    ...

All examples use `MockLLM` so they work without an API key. Set
`AG_*_LLM_PROVIDER=openai` (or `anthropic`, `ollama`) plus the matching
key to run against a real model.
"""
