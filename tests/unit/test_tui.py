"""Tests for TUI backend and app composition."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.config.schema import AegisConfig
from aegis.db.connection import reset_engine_cache
from aegis.providers.mock import MockProvider, text_response
from aegis.tui.app import AegisApp
from aegis.tui.backend import TuiBackend


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reset_engine_cache()
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("AEGIS_DB_PATH", str(tmp_path / "tui.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for key in ("AEGIS_PROVIDER", "AEGIS_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "README.md").write_text("# TUI Fixture\n", encoding="utf-8")
    yield ws
    reset_engine_cache()


@pytest.mark.asyncio
async def test_tui_backend_chat(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MockProvider(responses=[text_response("Hello from TUI backend.")])

    def fake_provider(config: AegisConfig, provider_name: str | None = None) -> MockProvider:
        _ = config, provider_name
        return mock

    monkeypatch.setattr("aegis.tui.backend.create_provider", fake_provider)

    backend = TuiBackend(workspace=workspace, trust_mode="yolo", provider="openai")
    sid = backend.create_session("test")
    assert sid.startswith("sess_")

    tokens: list[str] = []
    result = await backend.chat(
        "Say hi",
        on_token=lambda d: tokens.append(d),
    )
    assert result["error"] is None
    assert "Hello from TUI backend" in (result.get("output") or "")
    assert "".join(tokens) == result["output"]


def test_aegis_app_composes(workspace: Path) -> None:
    app = AegisApp(workspace=workspace, trust_mode="yolo")
    # Smoke: app constructs; full pilot optional
    assert app.workspace == workspace.resolve()
    assert app.TITLE == "Aegis Engineer"


def test_tui_cli_help() -> None:
    from typer.testing import CliRunner

    from aegis.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["tui", "--help"])
    assert result.exit_code == 0
    assert "Textual" in result.stdout or "interactive" in result.stdout.lower()
