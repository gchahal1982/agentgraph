from __future__ import annotations

from refresh_github import ACCEPT, API_VERSION, normalize_repository, preserve_last_good, snapshot

PAYLOAD = {
    "id": 1,
    "full_name": "o/r",
    "visibility": "public",
    "default_branch": "main",
    "archived": False,
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "pushed_at": "2026-01-01T00:00:00Z",
    "stargazers_count": 10,
    "watchers_count": 10,
    "subscribers_count": 3,
    "forks_count": 2,
    "open_issues_count": 1,
    "license": {"spdx_id": "Apache-2.0"},
}


def test_normalizes_actual_subscribers_not_watchers_alias():
    out = normalize_repository(PAYLOAD)
    assert out["stars"] == 10 and out["subscribers"] == 3 and "watchers" not in out
    snap = snapshot("/repos/o/r", PAYLOAD, requested_at="2026-07-17T00:00:00Z")
    assert (
        snap["api_version"] == API_VERSION
        and snap["accept"] == ACCEPT
        and len(snap["raw_payload_sha256"]) == 64
    )


def test_failure_preserves_last_immutable_snapshot(tmp_path):
    p = tmp_path / "last.json"
    p.write_text('{"status":"ok"}')
    out = preserve_last_good(p, "rate limited", "2026-07-17T00:00:00Z")
    assert out["last_good"] == {"status": "ok"} and out["stale"]
