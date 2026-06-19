"""Review a SOC2 control and attach evidence.

    uv run --all-packages python examples/compliance/review_control.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_compliance import ComplianceService


async def main() -> None:
    svc = ComplianceService.default(**example_llm())
    result = await svc.runner.arun(
        svc.review_graph, input={"framework": "soc2", "control": "CC6.1"}
    )
    print("output:", result.output)
    print("awaiting_signoff:", result.state.values.get("awaiting_signoff"))


if __name__ == "__main__":
    asyncio.run(main())
