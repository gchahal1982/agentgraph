"""Copy and verify the immutable canonical schema bundle for consumer repositories."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from _common import write_json


def bundle_hash(path: Path) -> str:
    h = hashlib.sha256()
    for file in sorted(path.glob("*.schema.json")):
        h.update(file.name.encode() + b"\0" + file.read_bytes())
    return h.hexdigest()


def sync(source: Path, target: Path, source_sha: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.schema.json"):
        old.unlink()
    for file in sorted(source.glob("*.schema.json")):
        shutil.copy2(file, target / file.name)
    write_json(
        target / "schema-version.json",
        {
            "schema_version": "1.0.0",
            "agentgraph_source_sha": source_sha,
            "schema_bundle_sha256": bundle_hash(target),
        },
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", type=Path, required=True)
    p.add_argument("--source-sha", required=True)
    a = p.parse_args()
    sync(a.source, a.target, a.source_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
