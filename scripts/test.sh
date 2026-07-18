#!/usr/bin/env bash
# Canonical test runner for AgentGraph.
#
# The host machine has a broken system pytest (Python 3.9 + web3 entry-point
# plugin) on PATH. Installing an ephemeral pytest with `--with` and running
# `python -m pytest` inside the uv-managed environment avoids it entirely.
set -euo pipefail
cd "$(dirname "$0")/.."
UV_BIN="${UV_BIN:-$(command -v uv || true)}"
if [[ -z "$UV_BIN" && -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
    echo "uv is required to run the test suite" >&2
    exit 127
fi
exec "$UV_BIN" run --all-packages --group dev \
    python -m pytest "${@:-tests}"
