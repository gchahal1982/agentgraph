"""Triage a patient intake message by acuity.

    uv run --all-packages python examples/healthcare/triage_intake.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_healthcare import HealthcareService


async def main() -> None:
    svc = HealthcareService.default(**example_llm())
    result = await svc.runner.arun(
        svc.intake_graph,
        input={
            "patient_id": "pat_001",
            "message": "I have chest pain and feel short of breath.",
        },
    )
    print("output:", result.output)
    print("acuity:", result.state.values.get("acuity"))
    print("awaiting_clinician:", result.state.values.get("awaiting_clinician"))


if __name__ == "__main__":
    asyncio.run(main())
