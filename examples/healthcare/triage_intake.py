"""Triage a patient intake message by acuity."""
import asyncio

from agentgraph_healthcare import HealthcareService


async def main() -> None:
    svc = HealthcareService.default()
    state = await svc.runner.runtime().run(
        svc.intake_graph,
        input={
            "patient_id": "pat_001",
            "message": "I have chest pain and feel short of breath.",
        },
    )
    print("output:", state.values.get("agent_output"))
    print("acuity:", state.values.get("acuity"))
    print("awaiting_clinician:", state.values.get("awaiting_clinician"))


if __name__ == "__main__":
    asyncio.run(main())
