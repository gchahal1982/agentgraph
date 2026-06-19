"""Core data types exchanged between agents, tools, and the runtime."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# JSON-serializable scalar / container values. This is a typing alias
# rather than a Pydantic field type, so it doesn't trigger recursive
# schema generation. Pydantic models that hold JSON-shaped state use
# `dict[str, Any]` or `list[Any]` directly.
JSONValue = Any
JSONObject = dict[str, Any]


class Role(str, Enum):
    """Speaker role for a chat message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """A single chat message.

    Mirrors the OpenAI/Anthropic chat shape so it can be projected to any
    provider. Tool messages carry a `tool_call_id`; assistant messages may
    carry `tool_calls`.
    """

    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    metadata: dict[str, JSONValue] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A model-emitted request to invoke a tool.

    `arguments` is parsed JSON. Tools declare their JSON schema and the
    runtime validates before dispatch.
    """

    id: str
    name: str
    arguments: dict[str, JSONValue]


class ToolResult(BaseModel):
    """Result of executing a tool call.

    `error` is set when the tool failed. The runtime converts this into a
    `tool` role message and may include the failure in the next model call.
    """

    tool_call_id: str
    name: str
    content: str
    error: str | None = None
    metadata: dict[str, JSONValue] = Field(default_factory=dict)


class Usage(BaseModel):
    """Token usage and cost for a single model call.

    Cost is computed by the provider module from the configured rates.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


class ModelResponse(BaseModel):
    """Unified model response across providers.

    Providers return either `message` (chat) or `text` (raw completion) plus
    usage information. Tool calls are extracted from the assistant message.
    """

    message: Message | None = None
    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter", "error"] = "stop"
    raw: dict[str, Any] = Field(default_factory=dict)


Message.model_rebuild()
