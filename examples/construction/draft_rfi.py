"""Draft an RFI from free-text field notes.

    uv run --all-packages python examples/construction/draft_rfi.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_construction import ConstructionService


async def main() -> None:
    svc = ConstructionService.default(**example_llm())
    result = await svc.runner.arun(
        svc.rfi_graph,
        input={
            "field_notes": 'Slab thickness at column line C looks like 6" not the 8" called out in spec 03 30 00.',
            "project_id": "PRJ-001",
        },
    )
    print("output:", result.output)


if __name__ == "__main__":
    asyncio.run(main())
