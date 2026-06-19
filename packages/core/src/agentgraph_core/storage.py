"""Storage configuration and backend selection.

AgentGraph persists two things durably: graph checkpoints (so runs survive
restarts and can be resumed) and the audit log (so every privileged action
is recorded). Both are selected from a single storage URL:

- ``sqlite:////absolute/path/agentgraph.db`` (default, single-node)
- ``sqlite://./relative/path.db``
- ``postgresql://user:pass@host:5432/dbname`` (multi-node)
- ``memory://`` (tests only; not durable)

The default, when ``AG_STORAGE_URL`` is unset, is a SQLite database under
the platform data directory (``~/.local/share/agentgraph/agentgraph.db`` on
Linux/macOS). This makes the out-of-the-box experience durable with no
external services.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from agentgraph_core.audit import (
    AuditLog,
    InMemoryAuditLog,
    PostgresAuditLog,
    SQLiteAuditLog,
)

DEFAULT_ENV_VAR = "AG_STORAGE_URL"


def default_storage_url() -> str:
    """Resolve the storage URL from the environment or fall back to SQLite."""
    explicit = os.environ.get(DEFAULT_ENV_VAR)
    if explicit:
        return explicit
    data_dir = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    ) / "agentgraph"
    return f"sqlite:///{data_dir / 'agentgraph.db'}"


def _sqlite_path(url: str) -> str:
    # Accept sqlite:///abs/path, sqlite://./rel/path, sqlite:///:memory:
    rest = url[len("sqlite://"):]
    if rest.startswith("/"):
        rest = rest[1:]  # strip the leading slash of sqlite:///
        return "/" + rest if not rest.startswith(":") else rest
    return rest


def audit_log_from_url(url: str | None = None) -> AuditLog:
    """Construct an `AuditLog` from a storage URL."""
    url = url or default_storage_url()
    scheme = urlparse(url).scheme
    if url.startswith("memory://") or scheme == "memory":
        return InMemoryAuditLog()
    if scheme.startswith("sqlite"):
        return SQLiteAuditLog(_sqlite_path(url))
    if scheme.startswith("postgres"):
        return PostgresAuditLog(url)
    raise ValueError(f"Unsupported storage URL scheme: {url!r}")


def sqlite_db_path(url: str | None = None) -> str | None:
    """Return the on-disk SQLite path for a storage URL, or None for others."""
    url = url or default_storage_url()
    if url.startswith("sqlite"):
        return _sqlite_path(url)
    return None
