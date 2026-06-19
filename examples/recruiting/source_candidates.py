"""Source and screen candidates for a role."""
import asyncio

from agentgraph_recruiting import RecruitingService


async def main() -> None:
    svc = RecruitingService.default()
    state = await svc.runner.runtime().run(
        svc.sourcing_graph,
        input={
            "role_title": "Senior Backend Engineer",
            "required_skills": ["python", "kubernetes", "postgres"],
            "years_experience": 5,
        },
    )
    print("output:", state.values.get("agent_output"))


if __name__ == "__main__":
    asyncio.run(main())
