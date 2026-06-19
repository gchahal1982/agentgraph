"""Recruiting tools: candidate search, resume parsing, scoring, scheduling."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from agentgraph_core.tools import ToolContext, tool
from agentgraph_core.types import JSONValue


class CandidatePool(Protocol):
    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]: ...
    def get(self, candidate_id: str) -> dict[str, Any] | None: ...
    def add(self, candidate: dict[str, Any]) -> dict[str, Any]: ...


class InMemoryCandidatePool:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}

    def seed(self, candidates: Iterable[dict[str, Any]]) -> None:
        for c in candidates:
            self._by_id[c["id"]] = c

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        q = query.lower()
        out: list[tuple[int, dict[str, Any]]] = []
        for c in self._by_id.values():
            haystack = " ".join(
                [
                    c.get("name", ""),
                    c.get("title", ""),
                    " ".join(c.get("skills", [])),
                    c.get("summary", ""),
                ]
            ).lower()
            score = sum(1 for word in q.split() if word in haystack)
            if score:
                out.append((score, c))
        out.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in out[:limit]]

    def get(self, candidate_id: str) -> dict[str, Any] | None:
        return self._by_id.get(candidate_id)

    def add(self, candidate: dict[str, Any]) -> dict[str, Any]:
        self._by_id[candidate["id"]] = candidate
        return candidate


_pool: CandidatePool = InMemoryCandidatePool()


def set_pool(pool: CandidatePool) -> None:
    global _pool
    _pool = pool


@tool(description="Search the candidate pool by free-text query (skills, title, etc).")
async def search_candidates(ctx: ToolContext, query: str, limit: int = 10) -> dict[str, JSONValue]:
    return {"candidates": _pool.search(query, limit=limit)}


@tool(description="Fetch a candidate's full resume by id.")
async def get_resume(ctx: ToolContext, candidate_id: str) -> dict[str, JSONValue]:
    cand = _pool.get(candidate_id)
    if not cand:
        return {"error": "not_found"}
    return {"candidate": cand}


@tool(description="Score a candidate against required skills. Returns 0-100.")
async def score_candidate(
    ctx: ToolContext, *, candidate_id: str, required_skills: list[str], years_experience: int
) -> dict[str, JSONValue]:
    cand = _pool.get(candidate_id)
    if not cand:
        return {"error": "not_found"}
    have = {s.lower() for s in cand.get("skills", [])}
    need = {s.lower() for s in required_skills}
    skill_match = len(have & need) / max(len(need), 1)
    yrs = cand.get("years_experience", 0)
    yr_factor = min(yrs / max(years_experience, 1), 1.0)
    score = int((skill_match * 0.7 + yr_factor * 0.3) * 100)
    return {
        "score": score,
        "skill_match_pct": round(skill_match * 100, 1),
        "years_experience": yrs,
        "matched_skills": sorted(have & need),
        "missing_skills": sorted(need - have),
    }


@tool(description="Draft a recruiter outreach message to a candidate.")
async def draft_outreach(
    ctx: ToolContext, *, candidate_name: str, role_title: str, hook: str = "your background"
) -> dict[str, JSONValue]:
    subject = f"{role_title} at our company - quick chat?"
    body = (
        f"Hi {candidate_name.split()[0]},\n\n"
        f"I came across {hook} and thought you'd be a great fit for our "
        f"{role_title} role. Would you be open to a 20-minute chat next week?\n\n"
        f"- Sent via AgentGraph recruiting"
    )
    return {"subject": subject, "body": body}


@tool(description="Schedule a phone screen between the candidate and a recruiter.")
async def schedule_screen(
    ctx: ToolContext, *, candidate_id: str, recruiter_id: str, slot: str
) -> dict[str, JSONValue]:
    return {
        "scheduled": True,
        "candidate_id": candidate_id,
        "recruiter_id": recruiter_id,
        "slot": slot,
    }


@tool(description="Hand the candidate off to a human recruiter; signals transition.")
async def handoff_to_recruiter(ctx: ToolContext, *, recruiter_id: str, reason: str) -> dict[str, JSONValue]:
    ctx.state["__goto__"] = "recruiter_handoff"
    ctx.state["recruiter_handoff"] = {"recruiter_id": recruiter_id, "reason": reason}
    return {"status": "queued", "recruiter_id": recruiter_id}
