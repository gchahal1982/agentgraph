"""Review a SOC2 control and attach evidence."""
import asyncio

from agentgraph_compliance import ComplianceService


async def main() -> None:
    svc = ComplianceService.default()
    state = await svc.reviewer.runtime().run(
        svc.review_graph, input={"framework": "soc2", "control": "CC6.1"}
    )
    print("output:", state.values.get("agent_output"))
    print("awaiting_signoff:", state.values.get("awaiting_signoff"))


if __name__ == "__main__":
    asyncio.run(main())
