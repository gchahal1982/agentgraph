# agentgraph-recruiting

Recruiting vertical pack: sourcing, screening, scheduling.

## Outcomes

- Source candidates from a candidate pool given a role description
- Screen resumes against required skills with a 0-100 fit score
- Schedule phone screens via the recruiter's calendar
- Hand off to a human recruiter for final-round review

## Quick start

```python
from agentgraph_recruiting import RecruitingService

svc = RecruitingService.default()
result = svc.source_candidates(
    role_title="Senior Backend Engineer",
    required_skills=["python", "kubernetes", "postgres"],
    years_experience=5,
)
print(result.output, result.cost_usd)
```

## Standalone service

```bash
uv run ag-recruiting --port 8084
curl -X POST http://localhost:8084/run/source -d '{
  "role_title": "Senior Backend Engineer",
  "required_skills": ["python", "kubernetes"]
}' -H 'content-type: application/json'
```

## Graphs

- `candidate_sourcing_graph` — top of funnel: from a role to a list of candidates to outreach.
- `candidate_screening_graph` — middle of funnel: from one resume to a screen verdict.

## Plug in your ATS

```python
from agentgraph_recruiting import set_pool
from agentgraph_recruiting.tools import InMemoryCandidatePool

pool = InMemoryCandidatePool()
pool.seed([{"id": "c1", "name": "Ada", "skills": ["python"], "years_experience": 5}])
set_pool(pool)
```

For production, implement the `CandidatePool` protocol against Greenhouse,
Lever, or your internal ATS.
