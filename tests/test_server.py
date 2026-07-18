"""FastAPI server: auth, health, and a real agent run over HTTP."""
from __future__ import annotations

import pytest
from agentgraph_llm.testing import register_test_provider, response, script
from agentgraph_runtime.graph import GraphBuilder
from agentgraph_runtime.node import NodeResult, node
from agentgraph_runtime.state import GraphState
from agentgraph_server.app import AppState, create_app
from agentgraph_server.registry import RegisteredAgent
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


def test_app_fails_closed_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AG_API_KEY", raising=False)
    monkeypatch.delenv("AG_ALLOW_INSECURE_NO_AUTH", raising=False)
    with pytest.raises(RuntimeError, match="AG_API_KEY is required"):
        AppState(storage_url="memory://")


def test_configured_api_key_wins_over_insecure_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AG_API_KEY", "secret-key")
    monkeypatch.setenv("AG_ALLOW_INSECURE_NO_AUTH", "1")
    state = AppState(storage_url="memory://")
    with TestClient(create_app(state, register_verticals=False)) as test_client:
        assert test_client.get("/agents").status_code == 401
        assert (
            test_client.get(
                "/agents", headers={"Authorization": "Bearer secret-key"}
            ).status_code
            == 200
        )


def test_explicit_insecure_local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AG_API_KEY", raising=False)
    monkeypatch.setenv("AG_ALLOW_INSECURE_NO_AUTH", "1")
    state = AppState(storage_url="memory://")
    with TestClient(create_app(state, register_verticals=False)) as test_client:
        assert test_client.get("/agents").status_code == 200


def test_thread_listing_requires_auth_and_returns_runs(client: TestClient) -> None:
    headers = {"Authorization": "Bearer secret-key"}
    thread = client.post("/threads", headers=headers).json()["thread_id"]
    register_test_provider()
    script("qualifier_agent", response(text="Qualified."))
    result = client.post(
        f"/threads/{thread}/run",
        headers=headers,
        json={"agent": "qualify_lead", "input": {"contact_email": "test@example.com"}},
    )
    assert result.status_code == 200, result.text
    assert client.get("/threads").status_code == 401
    listing = client.get("/threads", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["threads"][0]["thread_id"] == thread


def test_run_exception_is_absent_from_response_audit_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "arbitrary-customer-secret"

    @node("hard_failure")
    async def hard_failure(_state: GraphState) -> NodeResult:
        raise RuntimeError(secret)

    graph = GraphBuilder().add_node(hard_failure).set_entrypoint("hard_failure").compile()
    monkeypatch.setenv("AG_API_KEY", "secret-key")
    state = AppState(storage_url="memory://")
    state.registry.register_sync(
        RegisteredAgent("hard-failure", "hard failure", "test", graph)
    )
    with TestClient(
        create_app(state, register_verticals=False), raise_server_exceptions=False
    ) as test_client:
        headers = {"Authorization": "Bearer secret-key"}
        thread = test_client.post("/threads", headers=headers).json()["thread_id"]
        response = test_client.post(
            f"/threads/{thread}/run",
            headers=headers,
            json={"agent": "hard-failure", "input": {}},
        )
        audit_response = test_client.get(
            "/audit", headers=headers, params={"thread_id": thread}
        )
    assert response.status_code == 500
    assert response.json() == {"detail": "Agent execution failed"}
    assert secret not in response.text
    assert secret not in audit_response.text
    assert secret not in caplog.text


def test_swallowed_error_recovery_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "recovered-customer-secret"

    @node("flaky", swallow_errors=True, on_error="recover")
    async def flaky(_state: GraphState) -> NodeResult:
        raise RuntimeError(secret)

    @node("recover")
    async def recover(_state: GraphState) -> NodeResult:
        return NodeResult(updates={"output": "recovered"}, end=True)

    graph = (
        GraphBuilder()
        .add_node(flaky)
        .add_node(recover)
        .set_entrypoint("flaky")
        .compile()
    )
    monkeypatch.setenv("AG_API_KEY", "secret-key")
    state = AppState(storage_url="memory://")
    state.registry.register_sync(
        RegisteredAgent("recovery", "recovery", "test", graph)
    )
    with TestClient(create_app(state, register_verticals=False)) as test_client:
        headers = {"Authorization": "Bearer secret-key"}
        thread = test_client.post("/threads", headers=headers).json()["thread_id"]
        response = test_client.post(
            f"/threads/{thread}/run",
            headers=headers,
            json={"agent": "recovery", "input": {}},
        )
        runs = test_client.get(f"/threads/{thread}/runs", headers=headers)
    assert response.status_code == 200
    assert response.json()["output"] == "recovered"
    assert secret not in runs.text


def test_run_result_error_is_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "internal-runtime-detail"

    @node("soft_failure")
    async def soft_failure(_state: GraphState) -> NodeResult:
        return NodeResult(error=secret, end=True)

    graph = GraphBuilder().add_node(soft_failure).set_entrypoint("soft_failure").compile()
    monkeypatch.setenv("AG_API_KEY", "secret-key")
    state = AppState(storage_url="memory://")
    state.registry.register_sync(
        RegisteredAgent("soft-failure", "soft failure", "test", graph)
    )
    with TestClient(create_app(state, register_verticals=False)) as test_client:
        thread = test_client.post(
            "/threads", headers={"Authorization": "Bearer secret-key"}
        ).json()["thread_id"]
        response = test_client.post(
            f"/threads/{thread}/run",
            headers={"Authorization": "Bearer secret-key"},
            json={"agent": "soft-failure", "input": {}},
        )
    assert response.status_code == 500
    assert response.json() == {"detail": "Agent execution failed"}
    assert secret not in response.text
