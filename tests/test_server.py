"""FastAPI server endpoints."""
from __future__ import annotations

from agentgraph_server.app import create_app
from fastapi.testclient import TestClient


def test_health_endpoints() -> None:
    app = create_app()
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_agents_list_empty() -> None:
    app = create_app()
    client = TestClient(app)
    r = client.get("/agents")
    assert r.status_code == 200
    assert "agents" in r.json()


def test_create_thread() -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post("/threads")
    assert r.status_code == 201
    assert r.json()["thread_id"].startswith("thr_")
