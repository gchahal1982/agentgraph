"""Qualify a lead through the sales-ops graph.

Run against a real model by exporting AG_LLM_PROVIDER / AG_LLM_MODEL and the
provider key (e.g. OPENAI_API_KEY). Without those, this falls back to a
scripted local provider so it runs offline.

    uv run --all-packages python examples/sales_ops/qualify_lead.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_sales_ops import SalesOpsService


async def main() -> None:
    svc = SalesOpsService.default(**example_llm())
    result = await svc.runner.arun(svc.lead_graph, input={"contact_email": "ada@analytix.com"})
    print("run_id:", result.state.run.run_id)
    print("finished:", result.finished)
    print("cost_usd:", result.cost_usd)
    print("tokens:", result.tokens)
    print("output:", result.output)


if __name__ == "__main__":
    asyncio.run(main())
