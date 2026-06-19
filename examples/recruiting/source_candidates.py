"""Source candidates for a role.

    uv run --all-packages python examples/recruiting/source_candidates.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import example_llm
from agentgraph_recruiting import RecruitingService


async def main() -> None:
    svc = RecruitingService.default(**example_llm())
    result = await svc.runner.arun(
        svc.sourcing_graph,
        input={
            "role_title": "Senior Backend Engineer",
            "required_skills": ["python", "kubernetes", "postgres"],
            "years_experience": 5,
        },
    )
    print("output:", result.output)


if __name__ == "__main__":
    asyncio.run(main())
