"""CLI entry point for the server."""
from __future__ import annotations

import argparse
import os

import uvicorn

from agentgraph_server.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentgraph-server")
    parser.add_argument("--host", default=os.environ.get("AG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AG_PORT", "8080")))
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default=os.environ.get("AG_LOG_LEVEL", "info"))
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
