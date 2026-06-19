"""Triage a support ticket end-to-end.

    uv run --all-packages python examples/support_ops/triage_ticket.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_support_ops import SupportOpsService


async def main() -> None:
    svc = SupportOpsService.default(**example_llm())
    result = await svc.runner.arun(
        svc.triage_graph,
        input={
            "message": "How do I reset my password? I can't log in.",
            "requester_email": "user@example.com",
        },
    )
    print("output:", result.output)
    print("finished:", result.finished)
    print("cost_usd:", result.cost_usd)


if __name__ == "__main__":
    asyncio.run(main())
