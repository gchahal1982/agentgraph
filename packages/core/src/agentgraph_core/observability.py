"""Observability: spans, traces, and exporters.

The runtime wraps every node, tool, and model call in a span. Vertical
packs add domain-specific events (e.g. "deal.stage_changed") on top.
The default tracer is in-process and structured-logging only; OTel
exporters can be added without touching agent code.
"""
from __future__ import annotations

import contextlib
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import structlog

_log = structlog.get_logger("agentgraph.obs")


_current_span: ContextVar[Span | None] = ContextVar("ag_current_span", default=None)


@dataclass(slots=True)
class Span:
    """A single unit of work in a trace.

    Spans are nested via `current_span`. They emit to a `Tracer` on close
    so observers can record timings, costs, and metadata.
    """

    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_id: str | None = None
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    start: float = field(default_factory=time.time)
    end: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"
    error: str | None = None

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def event(self, name: str, **attrs: Any) -> None:
        self.events.append({"name": name, "ts": time.time(), **attrs})

    def fail(self, message: str) -> None:
        self.status = "error"
        self.error = message

    def finish(self) -> None:
        self.end = time.time()

    @property
    def duration_ms(self) -> float:
        if self.end is None:
            return (time.time() - self.start) * 1000.0
        return (self.end - self.start) * 1000.0


class Tracer(ABC):
    """Span sink. Production deployments export to OTel/Jaeger/etc."""

    @abstractmethod
    def on_span_end(self, span: Span) -> None: ...


class NoopTracer(Tracer):
    """Used in unit tests where span collection would be noise."""

    def on_span_end(self, span: Span) -> None:
        pass


class StructLogTracer(Tracer):
    """Writes a structured log line for every span.

    Pipe these into your aggregator of choice. The default formatter is
    JSON so log shippers (Vector, Fluent Bit) can parse it.
    """

    def __init__(self, level: str = "info") -> None:
        self._log = structlog.get_logger("agentgraph.span")
        self._level = level

    def on_span_end(self, span: Span) -> None:
        payload = {
            "span_id": span.span_id,
            "parent_id": span.parent_id,
            "trace_id": span.trace_id,
            "name": span.name,
            "duration_ms": round(span.duration_ms, 3),
            "status": span.status,
            "error": span.error,
            **span.attributes,
        }
        if span.status == "error":
            self._log.error(span.name, **payload)
        else:
            getattr(self._log, self._level)(span.name, **payload)


@contextlib.contextmanager
def span(name: str, **attrs: Any) -> Iterator[Span]:
    """Open a new span as a child of the current one (if any)."""
    parent = _current_span.get()
    s = Span(
        name=name,
        parent_id=parent.span_id if parent else None,
        trace_id=parent.trace_id if parent else uuid.uuid4().hex,
    )
    s.attributes.update(attrs)
    token = _current_span.set(s)
    try:
        yield s
    except Exception as e:
        s.fail(f"{type(e).__name__}: {e}")
        raise
    finally:
        s.finish()
        _current_span.reset(token)
        tracer = _get_tracer()
        tracer.on_span_end(s)


def trace(name: str, **attrs: Any):
    """Decorator equivalent of `span(...)` for sync functions."""
    def deco(fn):
        def wrap(*args, **kwargs):
            with span(name, **attrs):
                return fn(*args, **kwargs)
        return wrap
    return deco


_default_tracer: Tracer = StructLogTracer()


def set_tracer(tracer: Tracer) -> None:
    global _default_tracer
    _default_tracer = tracer


def _get_tracer() -> Tracer:
    return _default_tracer
