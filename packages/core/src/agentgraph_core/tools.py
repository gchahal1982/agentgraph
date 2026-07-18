"""Tool definition and execution primitives.

A `Tool` is a typed, schema-validated function the runtime can dispatch
agents to call. The runtime handles argument validation, error capture, audit
trails, and (optionally) policy enforcement.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, create_model

from agentgraph_core.errors import ToolError
from agentgraph_core.types import JSONValue, ToolResult

# A tool handler is either sync or async. Async is preferred for I/O work.
ToolHandler = Callable[
    ...,
    "str | dict[str, JSONValue] | ToolResult | Awaitable[ToolResult | str | dict[str, JSONValue]]",
]


@dataclass(slots=True)
class ToolContext:
    """Per-invocation context for a tool.

    Provides the tool with run-scoped state (run id, thread id, principal)
    and a `state` bag for passing values between tools in the same node.
    """

    run_id: str
    thread_id: str
    principal_id: str | None
    state: dict[str, JSONValue]


class Tool(BaseModel):
    """A named, schema-validated callable exposed to an agent.

    The runtime builds the JSON schema from the handler's signature using
    Pydantic models. Tools should be idempotent where possible and never
    silently swallow errors.
    """

    name: str
    description: str
    handler: Annotated[Any, Field(exclude=True)]
    args_schema: dict[str, Any] = Field(default_factory=dict)
    returns_json: bool = False
    requires_principal: bool = False

    model_config = {"arbitrary_types_allowed": True}

    async def __call__(self, ctx: ToolContext, **kwargs: JSONValue) -> ToolResult:
        try:
            result = self.handler(ctx, **kwargs)
            if inspect.isawaitable(result):
                result = await result
        except ToolError as e:
            return ToolResult(tool_call_id="", name=self.name, content="", error=str(e))
        except Exception as e:
            return ToolResult(
                tool_call_id="", name=self.name, content="", error=f"{type(e).__name__}: {e}"
            )

        if isinstance(result, ToolResult):
            return result
        if isinstance(result, str):
            return ToolResult(tool_call_id="", name=self.name, content=result)
        # dict / JSON object
        import orjson as _json

        return ToolResult(
            tool_call_id="",
            name=self.name,
            content=_json.dumps(result).decode("utf-8"),
        )


def _python_type_to_json_schema(tp: Any) -> dict[str, Any]:
    """Best-effort conversion of Python type hints to JSON schema fragments."""
    origin = get_origin(tp)
    args = get_args(tp)
    if tp is str or tp is None or tp is type(None):
        return {"type": "string"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if tp is bool:
        return {"type": "boolean"}
    if origin is list:
        item = args[0] if args else str
        return {"type": "array", "items": _python_type_to_json_schema(item)}
    if origin is dict:
        return {"type": "object", "additionalProperties": True}
    if origin is Annotated:
        return _python_type_to_json_schema(args[0])
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        schema = tp.model_json_schema()
        schema.pop("title", None)
        return schema
    return {"type": "string"}


def tool(
    name: str | None = None,
    description: str | None = None,
    *,
    returns_json: bool = False,
    requires_principal: bool = False,
) -> Callable[[ToolHandler], Tool]:
    """Decorator that turns a function into a `Tool`.

    Usage::

        @tool(description="Look up a customer by id")
        async def get_customer(ctx: ToolContext, customer_id: str) -> dict:
            return await db.customers.get(customer_id)

    The first positional argument (other than `ctx`) is treated as
    `ToolContext`. All other parameters are converted into JSON schema.
    """

    def _wrap(fn: ToolHandler) -> Tool:
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
        params = list(sig.parameters.values())
        if not params:
            raise TypeError(
                f"@tool function {fn.__name__!r} must take a ToolContext as its first parameter"
            )
        first_ann = hints.get(params[0].name, params[0].annotation)
        if first_ann is not ToolContext:
            raise TypeError(
                f"@tool function {fn.__name__!r} must take a ToolContext as its first parameter, "
                f"got {first_ann!r}"
            )
        fields: dict[str, Any] = {}
        for p in params[1:]:
            ann = hints.get(p.name, str)
            default = p.default if p.default is not inspect.Parameter.empty else ...
            fields[p.name] = (ann, default)
        model = create_model(f"{fn.__name__}_Args", **fields)
        schema = model.model_json_schema()
        schema.pop("title", None)
        tool_name = name or fn.__name__
        return Tool(
            name=tool_name,
            description=description or (inspect.getdoc(fn) or ""),
            handler=fn,
            args_schema=schema,
            returns_json=returns_json,
            requires_principal=requires_principal,
        )

    return _wrap
