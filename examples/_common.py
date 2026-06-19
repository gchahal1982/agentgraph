"""Shared setup for AgentGraph examples.

Examples run against a real LLM when one is configured (set ``AG_LLM_PROVIDER``,
``AG_LLM_MODEL`` and the provider's API key, e.g. ``OPENAI_API_KEY``). When no
provider is configured they fall back to a scripted local provider so the
example still runs end-to-end without network access or keys.

This module is for the examples only; it is not part of the shipped packages.
"""
from __future__ import annotations

import os


def example_llm() -> dict[str, str]:
    """Return Service.default(**kwargs) for the configured or scripted LLM.

    If ``AG_LLM_PROVIDER`` is set (e.g. ``openai``), use it. Otherwise register
    the scripted test provider and return its selector, plus an ephemeral
    storage URL so examples don't write to the durable default database.
    """
    if os.environ.get("AG_LLM_PROVIDER"):
        return {"storage_url": os.environ.get("AG_STORAGE_URL", "memory://")}

    # No real provider configured: use the scripted provider so the example
    # is runnable offline. This import is only available in a dev/test install.
    from agentgraph_llm.testing import register_test_provider, response, script

    register_test_provider()
    # A generic scripted reply that every agent node will fall back to.
    for node in (
        "qualifier_agent",
        "outreach_agent",
        "triage",
        "policy_reviewer",
        "sourcer",
        "fnol_intake",
        "rfi_drafter",
        "intake_triage",
    ):
        script(node, response(text="(scripted example response)", prompt_tokens=8, completion_tokens=4))
    return {"llm_provider": "test", "llm_model": "test-model", "storage_url": "memory://"}
