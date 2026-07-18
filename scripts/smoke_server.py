"""End-to-end server smoke test (run manually, not part of pytest).

    uv run --all-packages python scripts/smoke_server.py
"""
import os

os.environ.setdefault("AG_API_KEY", "smoke-key")
os.environ.setdefault("AG_LLM_PROVIDER", "test")
os.environ.setdefault("AG_LLM_MODEL", "test-model")
api_key = os.environ["AG_API_KEY"]

from agentgraph_llm.testing import register_test_provider, response, script  # noqa: E402
from agentgraph_server.app import AppState, create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

register_test_provider()
script("qualifier_agent", response(text="Qualified.", prompt_tokens=5, completion_tokens=2))

app = create_app(AppState(storage_url="memory://"), register_verticals=True)
with TestClient(app) as c:
    assert c.get("/healthz").json() == {"status": "ok"}
    print("healthz: ok")
    assert c.get("/agents").status_code == 401
    print("auth: unauthenticated request rejected (401)")
    h = {"Authorization": f"Bearer {api_key}"}
    agents = c.get("/agents", headers=h).json()["agents"]
    print("registered agents:", [a["name"] for a in agents])
    tid = c.post("/threads", headers=h).json()["thread_id"]
    print("thread:", tid)
    r = c.post(
        f"/threads/{tid}/run",
        headers=h,
        json={"agent": "qualify_lead", "input": {"contact_email": "ada@analytix.com"}},
    ).json()
    print("run finished:", r["finished"], "run_id:", r["run_id"])
    assert r["finished"] is True
print("SMOKE OK")
