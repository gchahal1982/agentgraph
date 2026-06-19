"""Triage a support ticket end-to-end."""
import asyncio

from agentgraph_support_ops import SupportOpsService


async def main() -> None:
    svc = SupportOpsService.default()
    state = await svc.runner.runtime().run(
        svc.triage_graph,
        input={
            "message": "How do I reset my password? I can't log in.",
            "requester_email": "user@example.com",
        },
    )
    print("output:", state.values.get("agent_output"))
    print("finished:", state.finished)
    print("cost_usd:", state.values.get("total_cost_usd"))


if __name__ == "__main__":
    asyncio.run(main())
