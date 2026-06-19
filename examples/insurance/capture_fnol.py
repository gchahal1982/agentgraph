"""Capture a First Notice of Loss from a customer description.

    uv run --all-packages python examples/insurance/capture_fnol.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_insurance import InsuranceService


async def main() -> None:
    svc = InsuranceService.default(**example_llm())
    result = await svc.runner.arun(
        svc.fnol_graph,
        input={
            "description": "My car was rear-ended at a stoplight on May 5. Bumper damage, no injuries.",
            "policy_id": "POL-1001",
        },
    )
    print("output:", result.output)
    print("awaiting_human_review:", result.state.values.get("awaiting_human_review"))


if __name__ == "__main__":
    asyncio.run(main())
