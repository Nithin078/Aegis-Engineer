"""HTTP server integration tests (in-process ASGI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from aegis.config.schema import AegisConfig
from aegis.db.connection import reset_engine_cache
from aegis.providers.mock import MockProvider, text_response, tool_then_text
from aegis.server.app import create_app


@pytest.fixture
def server_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reset_engine_cache()
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("AEGIS_DB_PATH", str(tmp_path / "test.db"))
    for key in (
        "AEGIS_PROVIDER",
        "AEGIS_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "AEGIS_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "workspace").mkdir()
    (tmp_path / "workspace" / "README.md").write_text(
        "# Server Fixture\n\nHello from tests.\n",
        encoding="utf-8",
    )
    yield tmp_path
    reset_engine_cache()


def _app(tmp_path: Path, mock: MockProvider | None = None) -> Any:
    provider = mock or MockProvider(responses=[text_response("hello from mock")])

    def factory(config: AegisConfig, name: str | None = None) -> MockProvider:
        _ = config, name
        return provider

    return create_app(
        config=AegisConfig(),
        db_path=tmp_path / "test.db",
        workspace=tmp_path / "workspace",
        provider_factory=factory,
        cors_origins=["*"],
    )


@pytest.mark.asyncio
async def test_health_and_session_crud(server_env: Path) -> None:
    app = _app(server_env)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/")
        assert r.status_code == 200
        assert "Aegis Engineer API" in r.text

        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        r = await client.post("/session", json={"title": "API test"})
        assert r.status_code == 201
        session = r.json()
        assert session["id"].startswith("sess_")
        assert session["title"] == "API test"

        r = await client.get(f"/session/{session['id']}")
        assert r.status_code == 200
        assert r.json()["message_count"] == 0

        r = await client.get(f"/session/{session['id']}/messages")
        assert r.status_code == 200
        assert r.json()["messages"] == []

        r = await client.get("/session/sess_missing")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_provider_and_tool_execute(server_env: Path) -> None:
    app = _app(server_env)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/provider")
        assert r.status_code == 200
        body = r.json()
        assert "providers" in body
        assert body["default"] == "anthropic"  # AegisConfig default

        r = await client.post(
            "/tool/execute",
            json={"tool": "read", "params": {"path": "README.md"}},
        )
        assert r.status_code == 200
        assert "Server Fixture" in r.json()["output"]


@pytest.mark.asyncio
async def test_chat_non_stream(server_env: Path) -> None:
    mock = MockProvider(responses=[text_response("Summary complete.")])
    app = _app(server_env, mock=mock)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"title": "Chat"})
        sid = r.json()["id"]

        r = await client.post(
            f"/session/{sid}/chat",
            json={"prompt": "Summarize", "stream": False},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["output"] == "Summary complete."
        assert data["error"] is None

        r = await client.get(f"/session/{sid}/messages")
        messages = r.json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_chat_sse_stream(server_env: Path) -> None:
    mock = MockProvider(responses=[text_response("streamed ok")])
    app = _app(server_env, mock=mock)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={"title": "SSE"})
        sid = r.json()["id"]

        async with client.stream(
            "POST",
            f"/session/{sid}/chat",
            json={"prompt": "hi", "stream": True},
        ) as response:
            assert response.status_code == 200
            body = (await response.aread()).decode("utf-8")

        assert "agent.start" in body or "agent.done" in body or "workflow.complete" in body
        assert "streamed ok" in body or "agent.token" in body or "workflow.complete" in body

        # Messages persisted
        r = await client.get(f"/session/{sid}/messages")
        assert len(r.json()["messages"]) == 2


@pytest.mark.asyncio
async def test_chat_with_tool(server_env: Path) -> None:
    first, second = tool_then_text(
        "read",
        json.dumps({"path": "README.md"}),
        "README mentions Server Fixture.",
    )
    mock = MockProvider(responses=[first, second])
    app = _app(server_env, mock=mock)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/session", json={})
        sid = r.json()["id"]
        r = await client.post(
            f"/session/{sid}/chat",
            json={"prompt": "Read the readme", "stream": False},
        )
        assert r.status_code == 200
        assert r.json()["tool_calls"] == 1
        assert "Fixture" in r.json()["output"] or "README" in r.json()["output"]
