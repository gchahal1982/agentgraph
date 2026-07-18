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
        prog="ag", description="AgentGraph CLI - agent runtime for business outcomes."
    )
    parser.add_argument("--server", default=os.environ.get("AG_SERVER", "http://localhost:8080"))
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AG_API_KEY"),
        help="Bearer token (defaults to AG_API_KEY)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("version", help="Print the CLI version")

    serve = sub.add_parser("serve", help="Start the HTTP server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    run = sub.add_parser("run", help="Run an agent on a registered server")
    run.add_argument("agent", help="Agent name")
    run.add_argument("--thread", help="Existing thread id")
    run.add_argument("--input", help="JSON-encoded input dict")
    run.add_argument("--principal-id", help="Principal id")
    run.add_argument("--principal-roles", help="Comma-separated roles")

    sub.add_parser("threads", help="List threads on the server")
    audit = sub.add_parser("audit", help="Query audit log")
    audit.add_argument("--run-id")
    audit.add_argument("--thread-id")
    audit.add_argument("--limit", type=int, choices=range(1, 1001), default=20, metavar="1..1000")
    sub.add_parser("agents", help="List registered agents")

    args = parser.parse_args(argv)
    handlers = {
        "serve": _serve,
        "run": _run,
        "threads": _list_threads,
        "audit": _audit,
        "agents": _agents,
    }
    if args.cmd == "version":
        print(f"ag {__version__}")
        return 0
    try:
        return handlers[args.cmd](args)
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        print(f"ag: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _headers(args: argparse.Namespace) -> dict[str, str]:
    return {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}


def _serve(args: argparse.Namespace) -> int:
    import uvicorn
    from agentgraph_server.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def _run(args: argparse.Namespace) -> int:
    decoded = json.loads(args.input) if args.input else {}
    if not isinstance(decoded, dict):
        raise ValueError("--input must decode to a JSON object")
    payload: dict[str, Any] = {"agent": args.agent, "input": decoded}
    if args.principal_id:
        payload["principal_id"] = args.principal_id
    if args.principal_roles:
        payload["principal_roles"] = [role.strip() for role in args.principal_roles.split(",")]
    thread_id = args.thread or _new_thread(args)
    with httpx.Client(base_url=args.server, timeout=120.0, headers=_headers(args)) as client:
        response = client.post(f"/threads/{thread_id}/run", json=payload)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2, default=str))
    return 0


def _list_threads(args: argparse.Namespace) -> int:
    _get_and_print(args, "/threads")
    return 0


def _audit(args: argparse.Namespace) -> int:
    params: dict[str, Any] = {"limit": args.limit}
    if args.run_id:
        params["run_id"] = args.run_id
    if args.thread_id:
        params["thread_id"] = args.thread_id
    _get_and_print(args, "/audit", params=params)
    return 0


def _agents(args: argparse.Namespace) -> int:
    _get_and_print(args, "/agents")
    return 0


def _get_and_print(
    args: argparse.Namespace, path: str, *, params: dict[str, Any] | None = None
) -> None:
    with httpx.Client(base_url=args.server, timeout=10.0, headers=_headers(args)) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2))


def _new_thread(args: argparse.Namespace) -> str:
    with httpx.Client(base_url=args.server, timeout=10.0, headers=_headers(args)) as client:
        response = client.post("/threads")
        response.raise_for_status()
        return str(response.json()["thread_id"])


if __name__ == "__main__":
    sys.exit(main())
