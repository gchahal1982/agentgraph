"""Portable helpers for the SOTA evidence contract."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
ARTIFACT_REF = re.compile(r"^(?:[A-Za-z0-9._/-]+|https://[^\s]+)$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_json(value).encode()
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def require_utc(value: str, field: str) -> str:
    if not RFC3339_UTC.fullmatch(value):
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp, not a date-only value")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo != UTC:
        raise ValueError(f"{field} must use UTC Z notation")
    return value


def check_sha256(value: str, field: str = "sha256") -> str:
    if not SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return value


def semantic_walk(value: Any, path: str = "$") -> list[str]:
    """Validate invariants JSON Schema cannot reliably express across all consumers."""
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            timestamp_key = key.endswith("_at") or key in {
                "cutoff",
                "observed_at",
                "retrieved_at",
                "valid_from",
                "expires_at",
            }
            if timestamp_key and isinstance(item, str) and not RFC3339_UTC.fullmatch(item):
                errors.append(f"{child}: expected RFC3339 UTC timestamp")
            hash_key = key.endswith("sha256") or (
                key.endswith("_hash") and key != "rule_version_hash"
            )
            if hash_key and isinstance(item, str) and not SHA256.fullmatch(item):
                errors.append(f"{child}: expected lowercase SHA-256")
            if (
                key in {"commit_sha", "tested_sha", "source_sha"}
                and isinstance(item, str)
                and not GIT_SHA.fullmatch(item)
            ):
                errors.append(f"{child}: expected full 40-character git SHA")
            if (
                key in {"artifact_path", "raw_artifact", "repository_path"}
                and isinstance(item, str)
                and (not ARTIFACT_REF.fullmatch(item) or ".." in Path(item).parts)
            ):
                errors.append(f"{child}: unsafe or mutable artifact reference")
            errors.extend(semantic_walk(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(semantic_walk(item, f"{path}[{index}]"))
    return errors


def duplicate_ids(value: Any) -> list[str]:
    """Detect duplicate primary IDs within each record collection.

    Reference fields intentionally repeat IDs, so uniqueness is scoped to arrays of
    records rather than all scalar ``*_id`` occurrences in a document.
    """
    primary_keys = (
        "claim_id",
        "source_id",
        "gap_id",
        "criterion_id",
        "subcriterion_id",
        "competitor_id",
        "run_id",
        "result_id",
        "gate_id",
        "pass_id",
        "id",
    )
    duplicates: list[str] = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, candidate in item.items():
                visit(candidate, f"{path}.{key}")
        elif isinstance(item, list):
            records = [candidate for candidate in item if isinstance(candidate, dict)]
            for key in primary_keys:
                values = [
                    (index, candidate[key])
                    for index, candidate in enumerate(records)
                    if isinstance(candidate.get(key), str)
                ]
                if not values:
                    continue
                seen: dict[str, int] = {}
                for index, candidate in values:
                    if candidate in seen:
                        duplicates.append(
                            f"{path}[{index}].{key}: duplicate ID {candidate!r} (first at {path}[{seen[candidate]}].{key})"
                        )
                    else:
                        seen[candidate] = index
                break
            for index, candidate in enumerate(item):
                visit(candidate, f"{path}[{index}]")

    visit(value, "$")
    return duplicates
