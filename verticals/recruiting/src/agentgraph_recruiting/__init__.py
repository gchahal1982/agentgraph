"""Recruiting vertical pack.

Outcomes:
- Source candidates from a job description and a candidate pool
- Screen resumes against required skills and produce a fit score
- Schedule phone screens via the recruiter's calendar
- Hand off to a human recruiter for the final round
"""
from agentgraph_recruiting.graphs import (
    build_recruiting_runner,
    candidate_screening_graph,
    candidate_sourcing_graph,
)
from agentgraph_recruiting.policies import RECRUITING_ROLES
from agentgraph_recruiting.service import RecruitingService
from agentgraph_recruiting.tools import (
    draft_outreach,
    get_resume,
    handoff_to_recruiter,
    schedule_screen,
    score_candidate,
    search_candidates,
)

__all__ = [
    "RECRUITING_ROLES",
    "RecruitingService",
    "build_recruiting_runner",
    "candidate_screening_graph",
    "candidate_sourcing_graph",
    "draft_outreach",
    "get_resume",
    "handoff_to_recruiter",
    "schedule_screen",
    "score_candidate",
    "search_candidates",
]
