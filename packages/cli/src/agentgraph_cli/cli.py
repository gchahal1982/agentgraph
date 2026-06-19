"""`ag` CLI implementation."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

from agentgraph_cli import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ag",
        description="AgentGraph CLI - agent runtime for business outcomes.",
    )
    parser.add_argument("--server", default=os.environ.get("AG_SERVER", "http://localhost:8080"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="Print the CLI version")

    p_serve = sub.add_parser("serve", help="Start the HTTP server")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8080)

    p_run = sub.add_parser("run", help="Run an agent on a registered server")
    p_run.add_argument("agent", help="Agent name")
    p_run.add_argument("--thread", help="Existing thread id")
    p_run.add_argument("--input", help="JSON-encoded input dict")
    p_run.add_argument("--principal-id", help="Principal id")
    p_run.add_argument("--principal-roles", help="Comma-separated roles")

    p_threads = sub.add_parser("threads", help="List threads on the server")
    _ = p_threads

    p_audit = sub.add_parser("audit", help="Query audit log")
    p_audit.add_argument("--run-id")
    p_audit.add_argument("--thread-id")
    p_audit.add_argument("--limit", type=int, default=20)

    p_agents = sub.add_parser("agents", help="List registered agents")
    _ = p_agents

    args = parser.parse_args(argv)

    if args.cmd == "version":
        print(f"ag {__version__}")
        return 0
    if args.cmd == "serve":
        return _serve(args)
    if args.cmd == "run":
        return _run(args)
    if args.cmd == "threads":
        return _list_threads(args)
    if args.cmd == "audit":
        return _audit(args)
    if args.cmd == "agents":
        return _agents(args)
    return 1


def _serve(args: argparse.Namespace) -> int:
    import uvicorn
    from agentgraph_server.app import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _run(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "agent": args.agent,
        "input": json.loads(args.input) if args.input else {},
    }
    if args.principal_id:
        payload["principal_id"] = args.principal_id
    if args.principal_roles:
        payload["principal_roles"] = [r.strip() for r in args.principal_roles.split(",")]
    thread_id = args.thread or _new_thread(args.server)
    with httpx.Client(base_url=args.server, timeout=120.0) as client:
        r = client.post(f"/threads/{thread_id}/run", json=payload)
        r.raise_for_status()
        print(json.dumps(r.json(), indent=2, default=str))
    return 0


def _list_threads(args: argparse.Namespace) -> int:
    with httpx.Client(base_url=args.server, timeout=10.0) as client:
        r = client.get("/threads")
        r.raise_for_status()
        print(json.dumps(r.json(), indent=2))
    return 0


def _audit(args: argparse.Namespace) -> int:
    params: dict[str, Any] = {"limit": args.limit}
    if args.run_id:
        params["run_id"] = args.run_id
    if args.thread_id:
        params["thread_id"] = args.thread_id
    with httpx.Client(base_url=args.server, timeout=10.0) as client:
        r = client.get("/audit", params=params)
        r.raise_for_status()
        print(json.dumps(r.json(), indent=2))
    return 0


def _agents(args: argparse.Namespace) -> int:
    with httpx.Client(base_url=args.server, timeout=10.0) as client:
        r = client.get("/agents")
        r.raise_for_status()
        print(json.dumps(r.json(), indent=2))
    return 0


def _new_thread(server: str) -> str:
    with httpx.Client(base_url=server, timeout=10.0) as client:
        r = client.post("/threads")
        r.raise_for_status()
        return r.json()["thread_id"]


if __name__ == "__main__":
    sys.exit(main())
