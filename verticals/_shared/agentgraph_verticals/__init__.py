"""Shared base for AgentGraph vertical packs.

Each vertical (sales-ops, support-ops, compliance, ...) implements:
- `agents.py`     - the agent specs and prompts for this vertical
- `tools.py`      - domain tools (CRM, ticketing, EHR, etc.)
- `graphs.py`     - the compiled graph(s) for this vertical
- `policies.py`   - role -> permission mappings and policy guards
- `service.py`    - a preconfigured FastAPI app or runner

This base gives them a consistent shape and a default `MockLLM` setup so
they work out-of-the-box in tests and CI without API keys.
"""
from agentgraph_verticals.base import VerticalMeta, VerticalPack, default_meta

__all__ = ["VerticalPack", "VerticalMeta", "default_meta"]