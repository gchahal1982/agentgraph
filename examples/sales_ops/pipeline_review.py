"""Review a sales account's pipeline."""
import asyncio

from agentgraph_sales_ops import SalesOpsService


async def main() -> None:
    svc = SalesOpsService.default()
    state = await svc.runner.runtime().run(
        svc.pipeline_graph, input={"account_id": "acct_analytix"}
    )
    print("output:", state.values.get("agent_output"))
    print("cost_usd:", state.values.get("total_cost_usd"))


if __name__ == "__main__":
    asyncio.run(main())
