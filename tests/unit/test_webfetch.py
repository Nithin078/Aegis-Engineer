"""Tests for webfetch / HTML scrape tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.config.schema import PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry
from aegis.tools.webfetch import _validate_url, html_to_text

runner = CliRunner()


def test_html_to_text_strips_script() -> None:
    html = """
    <html><head><title>Hello Page</title>
    <script>evil()</script><style>.x{}</style></head>
    <body><h1>Title</h1><p>Body text</p>
    <a href="https://example.com/docs">Docs</a>
    </body></html>
    """
    out = html_to_text(html, base_url="https://example.com/")
    assert out["title"] == "Hello Page"
    assert "Body text" in out["text"]
    assert "evil" not in out["text"]
    assert any(
        "example.com/docs" in (link.get("href") or "") for link in out["links"]
    )


def test_validate_blocks_localhost() -> None:
    assert _validate_url("http://localhost/secret") is not None
    assert _validate_url("http://127.0.0.1/") is not None
    assert _validate_url("ftp://example.com/") is not None
    assert _validate_url("https://example.com/docs") is None


@pytest.mark.asyncio
async def test_webfetch_tool_mocked(tmp_path: Path) -> None:
    eng = PermissionEngine(
        PermissionsConfig(default="allow", trust_mode="yolo", rules=[])
    )
    reg = create_default_registry(permission_engine=eng)
    assert reg.get("webfetch") is not None
    ctx = ToolContext(workspace_root=tmp_path, agent="chat", timeout=10.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example.com/page"
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.encoding = "utf-8"
    mock_resp.text = (
        "<html><head><title>Ex</title></head>"
        "<body><p>Hello scrape world</p></body></html>"
    )
    mock_resp.content = mock_resp.text.encode()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await reg.execute(
            "webfetch",
            {"url": "https://example.com/page", "include_links": False},
            ctx,
        )
    assert not result.error
    assert "Hello scrape world" in result.output
    assert result.metadata.get("status_code") == 200


@pytest.mark.asyncio
async def test_webfetch_blocks_private(tmp_path: Path) -> None:
    eng = PermissionEngine(
        PermissionsConfig(default="allow", trust_mode="yolo", rules=[])
    )
    reg = create_default_registry(permission_engine=eng)
    ctx = ToolContext(workspace_root=tmp_path, agent="chat", timeout=5.0)
    result = await reg.execute("webfetch", {"url": "http://127.0.0.1:8080/"}, ctx)
    assert result.error
    assert "private" in result.output.lower() or "refusing" in result.output.lower()


def test_cli_fetch_help() -> None:
    r = runner.invoke(app, ["fetch", "--help"])
    assert r.exit_code == 0
    assert "URL" in r.stdout or "url" in r.stdout.lower()
