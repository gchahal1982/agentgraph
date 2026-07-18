"""FastAPI server: auth, health, and a real agent run over HTTP."""
from __future__ import annotations

import pytest
from agentgraph_llm.testing import register_test_provider, response, script
from agentgraph_server.app import AppState, RunBody, create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    register_test_provider()
    monkeypatch.setenv("AG_API_KEY", "secret-key")
    monkeypatch.setenv("AG_LLM_PROVIDER", "test")
    monkeypatch.setenv("AG_LLM_MODEL", "test-model")
    # Use ephemeral storage and register verticals so /run works end-to-end.
    state = AppState(storage_url="memory://")
    app = create_app(state, register_verticals=True)
    with TestClient(app) as c:
        yield c


def test_run_body_is_module_scoped_json_request_body(client: TestClient) -> None:
    schema = client.app.openapi()
    operation = schema["paths"]["/threads/{thread_id}/run"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]

    assert RunBody.__qualname__ == "RunBody"
    assert request_schema == {"$ref": "#/components/schemas/RunBody"}
    assert "body" not in {parameter["name"] for parameter in operation.get("parameters", [])}


def test_healthz_is_public(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_reports_registered_agents(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert int(r.json()["agents"]) >= 1


def test_agents_requires_auth(client: TestClient) -> None:
    r = client.get("/agents")
    assert r.status_code == 401


def test_agents_listed_with_auth(client: TestClient) -> None:
    r = client.get("/agents", headers={"Authorization": "Bearer secret-key"})
    assert r.status_code == 200
    names = {a["name"] for a in r.json()["agents"]}
    assert "qualify_lead" in names


def test_create_thread_requires_auth(client: TestClient) -> None:
    assert client.post("/threads").status_code == 401
    r = client.post("/threads", headers={"Authorization": "Bearer secret-key"})
    assert r.status_code == 201
    assert r.json()["thread_id"].startswith("thr_")


def test_run_agent_end_to_end(client: TestClient) -> None:
    register_test_provider()
    script("qualifier_agent", response(text="Qualified.", prompt_tokens=5, completion_tokens=2))
    headers = {"Authorization": "Bearer secret-key"}
    thread = client.post("/threads", headers=headers).json()["thread_id"]
    r = client.post(
        f"/threads/{thread}/run",
        headers=headers,
        json={"agent": "qualify_lead", "input": {"contact_email": "ada@analytix.com"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["finished"] is True
    assert body["thread_id"] == thread


def test_unknown_agent_404(client: TestClient) -> None:
    headers = {"Authorization": "Bearer secret-key"}
    thread = client.post("/threads", headers=headers).json()["thread_id"]
    r = client.post(
        f"/threads/{thread}/run", headers=headers, json={"agent": "does_not_exist", "input": {}}
    )
    assert r.status_code == 404
