"""Create immutable normalized GitHub snapshots; never infer capability."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _common import digest, read_json, write_json

API_VERSION = "2022-11-28"
ACCEPT = "application/vnd.github+json"


def normalize_repository(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository_id": payload["id"],
        "full_name": payload["full_name"],
        "visibility": payload.get("visibility", "private" if payload.get("private") else "public"),
        "default_branch": payload["default_branch"],
        "archived": bool(payload.get("archived")),
        "created_at": payload["created_at"],
        "updated_at": payload["updated_at"],
        "pushed_at": payload.get("pushed_at"),
        "stars": payload.get("stargazers_count", 0),
        "forks": payload.get("forks_count", 0),
        "subscribers": payload.get("subscribers_count", 0),
        "open_issues": payload.get("open_issues_count", 0),
        "license": (payload.get("license") or {}).get("spdx_id"),
    }


def snapshot(
    endpoint: str,
    payload: dict[str, Any],
    *,
    requested_at: str,
    etag: str | None = None,
    rate_limit: dict[str, Any] | None = None,
    workflow_url: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_repository(payload)
    return {
        "endpoint": endpoint,
        "requested_at": requested_at,
        "etag": etag,
        "api_version": API_VERSION,
        "accept": ACCEPT,
        "rate_limit": rate_limit or {},
        "workflow_url": workflow_url,
        "normalized": normalized,
        "raw_payload_sha256": digest(payload),
    }


def preserve_last_good(target: Path, failure: str, at: str) -> dict[str, Any]:
    previous = read_json(target) if target.exists() else None
    return {
        "status": "blocked",
        "stale": True,
        "failure": failure,
        "failed_at": at,
        "last_good": previous,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--endpoint", required=True)
    p.add_argument("--at")
    a = p.parse_args()
    at = a.at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    write_json(a.output, snapshot(a.endpoint, read_json(a.input), requested_at=at))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
