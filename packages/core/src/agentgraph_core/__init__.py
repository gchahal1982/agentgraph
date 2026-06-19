"""AgentGraph core: primitives for agents, tools, memory, audit, and RBAC.

The runtime is intentionally framework-agnostic. Vertical packs compose these
primitives to ship opinionated, production-ready solutions for specific
business outcomes.
"""
from agentgraph_core.audit import AuditEvent, AuditLog, InMemoryAuditLog
from agentgraph_core.errors import AgentGraphError, PolicyError, ToolError
from agentgraph_core.ids import new_id, new_run_id, new_thread_id
from agentgraph_core.memory import InMemoryMemory, Memory
from agentgraph_core.observability import NoopTracer, Tracer, span, trace
from agentgraph_core.rbac import Permission, Principal, RbacRole
from agentgraph_core.tools import Tool, ToolContext, tool
from agentgraph_core.types import JSONValue, Message, Role, ToolCall, ToolResult

__all__ = [
    "new_id",
    "new_thread_id",
    "new_run_id",
    "Message",
    "Role",
    "ToolCall",
    "ToolResult",
    "JSONValue",
    "Tool",
    "ToolContext",
    "tool",
    "Memory",
    "InMemoryMemory",
    "AuditEvent",
    "AuditLog",
    "InMemoryAuditLog",
    "Principal",
    "RbacRole",
    "Permission",
    "trace",
    "span",
    "Tracer",
    "NoopTracer",
    "AgentGraphError",
    "ToolError",
    "PolicyError",
]
