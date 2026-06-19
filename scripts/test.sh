#!/usr/bin/env bash
# Canonical test runner for AgentGraph.
#
# The host machine has a broken system pytest (Python 3.9 + web3 entry-point
# plugin) on PATH. Installing an ephemeral pytest with `--with` and running
# `python -m pytest` inside the uv-managed environment avoids it entirely.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --all-packages --with pytest --with pytest-asyncio \
    python -m pytest "${@:-tests}"
