"""Review a sales account's pipeline.

    uv run --all-packages python examples/sales_ops/pipeline_review.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_sales_ops import SalesOpsService


async def main() -> None:
    svc = SalesOpsService.default(**example_llm())
    result = await svc.runner.arun(svc.pipeline_graph, input={"account_id": "acct_analytix"})
    print("output:", result.output)
    print("cost_usd:", result.cost_usd)


if __name__ == "__main__":
    asyncio.run(main())
