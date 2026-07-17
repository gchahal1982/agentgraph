from __future__ import annotations

from datetime import UTC, datetime

from refresh_context import DOC_SECTIONS, docs_score, normalize, response_stats

NOW = datetime(2026, 7, 17, tzinfo=UTC)


def review(value: bool = True) -> dict[str, object]:
    return {
        "reviewer": "r",
        "sections": {section: value for section in DOC_SECTIONS},
        "reviewed_at": "2026-07-17T00:00:00Z",
    }


def test_human_cadence_excludes_automation_and_deduplicates_identities() -> None:
    raw = {
        "product_id": "p",
        "mailmap": {"old@example.com": "alice"},
        "commits": [
            {
                "committed_at": "2026-07-16T00:00:00Z",
                "author": {"email": "OLD@example.com"},
            },
            {
                "committed_at": "2026-07-15T00:00:00Z",
                "author": {"name": "Alice"},
            },
            {
                "committed_at": "2026-05-01T00:00:00Z",
                "author": {"login": "deps[bot]", "bot": True},
            },
            {
                "committed_at": "2025-01-01T00:00:00Z",
                "author": {"name": "release automation", "service_account": True},
            },
            {
                "committed_at": "2026-04-01T00:00:00Z",
                "author": {"name": "Merge Author"},
                "merge": True,
            },
            {
                "committed_at": "2026-03-01T00:00:00Z",
                "author": {"name": "Fork Author"},
                "fork": True,
            },
        ],
        "releases": [
            {
                "version": "1.0",
                "artifact_sha256": "a" * 64,
                "published_at": "2026-07-01T00:00:00Z",
            },
            {
                "version": "1.0",
                "artifact_sha256": "a" * 64,
                "published_at": "2026-07-01T00:00:00Z",
            },
            {
                "version": "2.0rc",
                "artifact_sha256": "b" * 64,
                "published_at": "2026-07-02T00:00:00Z",
                "prerelease": True,
            },
        ],
        "documentation_reviews": [review(), review()],
    }

    output = normalize(raw, NOW)

    assert output["contributors"]["human_unique"] == 1
    assert output["commits"] == {
        "days_30": 2,
        "days_90": 2,
        "days_365": 2,
        "lifetime": 2,
        "active_weeks": 1,
        "median_per_week": 2,
    }
    assert output["releases"]["stable_lifetime"] == 1
    assert output["releases"]["prerelease_365"] == 1


def test_docs_disagreement_requires_adjudication() -> None:
    other = review()
    other["sections"]["security"] = False
    assert docs_score([review(), other]) == (None, True)
    assert docs_score([review(), review()]) == (10, False)


def test_response_exclusions_reopen_final_close_empty_and_small_samples() -> None:
    items = [
        {
            "opened_at": "2026-07-01T00:00:00Z",
            "responses": [
                {"at": "2026-07-01T01:00:00Z", "bot": True, "maintainer": True},
                {"at": "2026-07-01T02:00:00Z", "maintainer": True},
            ],
            "final_closed_at": "2026-07-03T00:00:00Z",
            "reopened": True,
        },
        {"opened_at": "2026-07-01T00:00:00Z", "draft": True},
        {"opened_at": "2026-07-01T00:00:00Z", "private": True},
    ]
    output = response_stats(items, NOW)
    assert output["first_response"]["sample_size"] == 1
    assert output["first_response"]["median_hours"] == 2
    assert output["close_or_merge"]["median_hours"] == 48
    assert response_stats([], NOW)["first_response"]["median_hours"] is None
