"""Identifier generation for runs, threads, and entities."""
from __future__ import annotations

import ulid as _ulid


def new_id() -> str:
    """Generate a sortable, URL-safe unique identifier (ULID)."""
    return str(_ulid.new())


def new_run_id() -> str:
    """Generate a run-scoped identifier with a `run_` prefix for log clarity."""
    return f"run_{new_id()}"


def new_thread_id() -> str:
    """Generate a thread (conversation) identifier with a `thr_` prefix."""
    return f"thr_{new_id()}"
