"""Draft an RFI from free-text field notes."""
import asyncio

from agentgraph_construction import ConstructionService


async def main() -> None:
    svc = ConstructionService.default()
    state = await svc.runner.runtime().run(
        svc.rfi_graph,
        input={
            "field_notes": "Slab thickness at column line C looks like 6\" not the 8\" called out in spec 03 30 00.",
            "project_id": "PRJ-001",
        },
    )
    print("output:", state.values.get("agent_output"))


if __name__ == "__main__":
    asyncio.run(main())
