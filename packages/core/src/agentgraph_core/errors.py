"""Common AgentGraph errors.

Vertical packs raise domain errors that subclass these. The runtime
catches the base class to ensure failures surface as audit events and
span statuses.
"""
from __future__ import annotations


class AgentGraphError(Exception):
    """Base class for all AgentGraph errors."""


class ToolError(AgentGraphError):
    """Raised by a tool to signal a user-visible failure.

    Other exceptions are converted to `error` strings in the tool result
    so the model can react to them.
    """


class PolicyError(AgentGraphError):
    """A tool or node was invoked without the required permission."""


class GraphError(AgentGraphError):
    """The graph could not be executed: missing node, cycle without exit, etc."""


class CheckpointError(AgentGraphError):
    """A checkpoint backend could not save or restore state."""


class LLMError(AgentGraphError):
    """An LLM provider returned an unrecoverable error."""


class HandoffError(AgentGraphError):
    """A human handoff could not be completed (queue, channel, etc.)."""
