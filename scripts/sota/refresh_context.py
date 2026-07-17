"""Normalize competitive-context snapshots deterministically."""

from __future__ import annotations

import argparse
import statistics
from collections import Counter
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

from _common import read_json, write_json

WINDOWS = (30, 90, 365)
DOC_SECTIONS = (
    "install",
    "architecture",
    "api_reference",
    "examples",
    "operations",
    "security",
    "troubleshooting",
    "migrations",
    "governance",
    "freshness",
)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
    return ordered[index]


def human_identity(author: dict[str, Any], mailmap: dict[str, str]) -> str | None:
    """Return a normalized human identity, or ``None`` for automation."""
    login = str(author.get("login", "")).casefold()
    email = str(author.get("email", "")).casefold()
    name = str(author.get("name", "")).strip().casefold()
    if (
        author.get("bot")
        or login.endswith("[bot]")
        or "bot@" in email
        or author.get("service_account")
    ):
        return None
    key = email or login or name
    return mailmap.get(key, key) if key else None


def docs_score(reviews: list[dict[str, Any]]) -> tuple[int | None, bool]:
    if len(reviews) != 2:
        return None, True
    scores = []
    for review in reviews:
        values = review["sections"]
        if set(values) != set(DOC_SECTIONS):
            raise ValueError("documentation review must cover all ten rubric sections")
        scores.append(sum(bool(values[name]) for name in DOC_SECTIONS))
    if reviews[0]["sections"] != reviews[1]["sections"]:
        return None, True
    return scores[0], False


def distribution_stats(values: list[float]) -> dict[str, Any]:
    return {
        "sample_size": len(values),
        "median_hours": statistics.median(values) if values else None,
        "p90_hours": percentile(values, 0.9),
    }


def response_stats(items: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    response_hours: list[float] = []
    closure_hours: list[float] = []
    open_age_hours: list[float] = []
    for item in items:
        if item.get("draft") or item.get("duplicate") or item.get("private") or item.get("bot"):
            continue
        opened = parse_timestamp(item["opened_at"])
        responses = [
            parse_timestamp(response["at"])
            for response in item.get("responses", [])
            if not response.get("bot") and response.get("maintainer")
        ]
        if responses:
            response_hours.append((min(responses) - opened).total_seconds() / 3600)
        if final_close := item.get("final_closed_at"):
            closure_hours.append((parse_timestamp(final_close) - opened).total_seconds() / 3600)
        else:
            open_age_hours.append((now - opened).total_seconds() / 3600)
    return {
        "first_response": distribution_stats(response_hours),
        "close_or_merge": distribution_stats(closure_hours),
        "open_age": distribution_stats(open_age_hours),
    }


def normalized_human_commits(
    raw_commits: list[dict[str, Any]], mailmap: dict[str, str]
) -> list[tuple[dict[str, Any], str]]:
    """Filter non-cadence commits and attach each normalized human identity."""
    commits: list[tuple[dict[str, Any], str]] = []
    for commit in raw_commits:
        if commit.get("merge") or commit.get("fork") or commit.get("mirror"):
            continue
        identity = human_identity(commit["author"], mailmap)
        if identity is not None:
            commits.append((commit, identity))
    return commits


def commit_context(commits: list[tuple[dict[str, Any], str]], now: datetime) -> dict[str, Any]:
    committed_at = [parse_timestamp(commit["committed_at"]) for commit, _identity in commits]
    commits_per_week = Counter(value.strftime("%G-%V") for value in committed_at)
    return {
        **{
            f"days_{days}": sum((now - value).days < days for value in committed_at)
            for days in WINDOWS
        },
        "lifetime": len(commits),
        "active_weeks": len(commits_per_week),
        "median_per_week": statistics.median(commits_per_week.values()) if commits_per_week else 0,
    }


def release_context(releases: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    deduplicated = {
        (release["version"], release["artifact_sha256"]): release for release in releases
    }
    stable_dates = sorted(
        parse_timestamp(release["published_at"])
        for release in deduplicated.values()
        if not release.get("prerelease")
    )
    intervals = [
        (later - earlier).total_seconds() / 86400 for earlier, later in pairwise(stable_dates)
    ]
    return {
        "stable_365": sum((now - value).days < 365 for value in stable_dates),
        "stable_lifetime": len(stable_dates),
        "prerelease_365": sum(
            (now - parse_timestamp(release["published_at"])).days < 365
            for release in deduplicated.values()
            if release.get("prerelease")
        ),
        "median_days": statistics.median(intervals) if intervals else None,
        "days_since_latest": (now - stable_dates[-1]).days if stable_dates else None,
        "deduplication": "version+artifact",
    }


def normalize(raw: dict[str, Any], now: datetime) -> dict[str, Any]:
    mailmap = {key.casefold(): value.casefold() for key, value in raw.get("mailmap", {}).items()}
    commits = normalized_human_commits(raw.get("commits", []), mailmap)
    contributors = {identity for _commit, identity in commits}
    reviews = raw.get("documentation_reviews", [])
    documentation_score, needs_adjudication = docs_score(reviews)
    return {
        "product_id": raw["product_id"],
        "collected_at": now.isoformat().replace("+00:00", "Z"),
        "windows": {"days_30": 30, "days_90": 90, "days_365": 365, "lifetime": "lifetime"},
        "contributors": {
            "human_unique": len(contributors),
            "normalization": "mailmap-verified-casefold-bot-excluded",
        },
        "commits": commit_context(commits, now),
        "releases": release_context(raw.get("releases", []), now),
        "documentation_reviews": reviews,
        "documentation_score": documentation_score,
        "documentation_adjudication_required": needs_adjudication,
        "issues": response_stats(raw.get("issues", []), now),
        "pull_requests": response_stats(raw.get("pull_requests", []), now),
        "community": raw.get("community", {}),
        "deployment": raw.get("deployment", []),
        "license": raw.get("license", "unknown"),
        "limitations": raw.get("limitations", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--at", required=True)
    args = parser.parse_args()
    collected_at = parse_timestamp(args.at).astimezone(UTC)
    write_json(args.output, normalize(read_json(args.input), collected_at))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
