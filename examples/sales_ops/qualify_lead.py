"""Qualify a lead through the sales-ops graph."""
import asyncio

from agentgraph_sales_ops import SalesOpsService


async def main() -> None:
    svc = SalesOpsService.default()
    state = await svc.runner.runtime().run(
        svc.lead_graph, input={"contact_email": "ada@analytix.com"}
    )
    print("run_id:", state.run.run_id)
    print("finished:", state.finished)
    print("cost_usd:", state.values.get("total_cost_usd"))
    print("tokens:", state.values.get("total_tokens"))
    print("output:", state.values.get("agent_output") or state.values.get("qualification"))


if __name__ == "__main__":
    asyncio.run(main())
