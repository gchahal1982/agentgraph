"""Support-ops tools: knowledge base, ticketing, sentiment, escalation.

Backends are pluggable via `set_kb(...)` and `set_ticketing(...)`. The
default `InMemoryKB`/`InMemoryTicketing` implement the protocols so a service
runs with no external system; in production you implement the same protocols
against Zendesk, Intercom, or a Notion/Confluence knowledge base.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue

# --- backends ---


class KnowledgeBase(Protocol):
    def search(self, query: str, *, limit: int = 3) -> list[dict[str, Any]]: ...
    def add(self, article: dict[str, Any]) -> dict[str, Any]: ...


class InMemoryKB:
    def __init__(self) -> None:
        self._articles: list[dict[str, Any]] = []
        self._id = 0

    def seed(self, articles: Iterable[dict[str, Any]]) -> None:
        for a in articles:
            self.add(a)

    def add(self, article: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        a = {**article, "id": article.get("id", f"kb_{self._id}")}
        self._articles.append(a)
        return a

    def search(self, query: str, *, limit: int = 3) -> list[dict[str, Any]]:
        q = query.lower()
        scored: list[tuple[int, dict[str, Any]]] = []
        for a in self._articles:
            text = (a.get("title", "") + " " + a.get("body", "")).lower()
            score = sum(1 for word in q.split() if word in text)
            if score:
                scored.append((score, a))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:limit]]


class Ticketing(Protocol):
    def create(self, ticket: dict[str, Any]) -> dict[str, Any]: ...
    def update(self, ticket_id: str, **fields: Any) -> dict[str, Any]: ...


class InMemoryTicketing:
    def __init__(self) -> None:
        self._tickets: dict[str, dict[str, Any]] = {}
        self._id = 0

    def create(self, ticket: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        tid = f"t_{self._id:05d}"
        self._tickets[tid] = {"id": tid, "status": "open", **ticket}
        return self._tickets[tid]

    def update(self, ticket_id: str, **fields: Any) -> dict[str, Any]:
        t = self._tickets.setdefault(ticket_id, {"id": ticket_id, "status": "open"})
        t.update(fields)
        return t


# Singletons (verticals inject their own in production).
_kb: KnowledgeBase = InMemoryKB()
_ticketing: Ticketing = InMemoryTicketing()


def set_kb(kb: KnowledgeBase) -> None:
    global _kb
    _kb = kb


def set_ticketing(t: Ticketing) -> None:
    global _ticketing
    _ticketing = t


def get_kb() -> KnowledgeBase:
    return _kb


def get_ticketing() -> Ticketing:
    return _ticketing


# --- tool definitions ---


@tool(description="Search the knowledge base for articles matching a query.")
async def kb_search(ctx: ToolContext, query: str, limit: int = 3) -> dict[str, JSONValue]:
    hits = _kb.search(query, limit=limit)
    return {"hits": hits, "count": len(hits)}


@tool(description="Add an article to the knowledge base. Use this when you discover a new common question.")
async def kb_add_article(ctx: ToolContext, *, title: str, body: str, tags: list[str] | None = None) -> dict[str, JSONValue]:
    return {"article": _kb.add({"title": title, "body": body, "tags": tags or []})}


@tool(description="Create a support ticket for the customer's issue.")
async def ticket_create(
    ctx: ToolContext,
    *,
    subject: str,
    body: str,
    requester_email: str,
    priority: str = "normal",
    tags: list[str] | None = None,
) -> dict[str, JSONValue]:
    return {"ticket": _ticketing.create({
        "subject": subject,
        "body": body,
        "requester_email": requester_email,
        "priority": priority,
        "tags": tags or [],
    })}


@tool(description="Update fields on an existing ticket (status, priority, assignee, tags).")
async def ticket_update(ctx: ToolContext, ticket_id: str, **fields: JSONValue) -> dict[str, JSONValue]:
    return {"ticket": _ticketing.update(ticket_id, **fields)}


@tool(
    description=(
        "Score the sentiment of a piece of text from -1 (very negative) "
        "to +1 (very positive). Use this to decide whether to escalate."
    )
)
async def sentiment_score(ctx: ToolContext, text: str) -> dict[str, JSONValue]:
    text = text.lower()
    pos = sum(text.count(w) for w in ("great", "thanks", "love", "awesome", "perfect", "happy"))
    neg = sum(text.count(w) for w in ("angry", "broken", "terrible", "frustrat", "complain", "refund", "cancel"))
    score = max(-1.0, min(1.0, (pos - neg) / 5.0))
    return {"score": score, "positive": pos, "negative": neg}


@tool(description="Escalate the conversation to a human agent; signals a transition out of the agent node.")
async def escalate_to_human(
    ctx: ToolContext,
    *,
    reason: str,
    priority: str = "normal",
    queue: str = "tier-2",
) -> dict[str, JSONValue]:
    ctx.state["__goto__"] = "escalate"
    ctx.state["escalation"] = {"reason": reason, "priority": priority, "queue": queue}
    return {"status": "queued", "reason": reason, "queue": queue}
