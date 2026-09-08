import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(index, monkeypatch):
    import voice.server as server
    importlib.reload(server)
    monkeypatch.setattr(server, "get_index", lambda: index)
    return TestClient(server.app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["mps_indexed"] == 4
    assert body["assemblyai_configured"] is False


def test_ask_post(client):
    r = client.post("/api/ask", json={"question": "attendance of Asha Verma"})
    assert r.status_code == 200
    assert "88 percent" in r.json()["answer"]


def test_tool_post_shape(client):
    r = client.post("/tools/ask", json={"question": "net worth of Bhuvan Singh"})
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert "8.2 crore" in body["answer"]


def test_tool_get_shape(client):
    r = client.get("/tools/ask", params={"question": "best MPs in Test Pradesh"})
    assert r.status_code == 200
    assert "Asha Verma" in r.json()["answer"]


def test_voice_token_503_without_key(client, monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    r = client.get("/api/voice-token")
    assert r.status_code == 503


def test_home_and_talk_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/talk").status_code == 200
    assert client.get("/static/talk.js").status_code == 200
