"""Capture a First Notice of Loss from a customer description."""
import asyncio

from agentgraph_insurance import InsuranceService


async def main() -> None:
    svc = InsuranceService.default()
    state = await svc.runner.runtime().run(
        svc.fnol_graph,
        input={
            "description": "My car was rear-ended at a stoplight on May 5. Bumper damage, no injuries.",
            "policy_id": "POL-1001",
        },
    )
    print("output:", state.values.get("agent_output"))
    print("awaiting_human_review:", state.values.get("awaiting_human_review"))


if __name__ == "__main__":
    asyncio.run(main())
