"""Tests for `aegis run` CLI with a mocked provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.db.connection import reset_engine_cache
from aegis.providers.mock import MockProvider, text_response, tool_then_text

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Project README\n\nPhase 3 test.\n", encoding="utf-8")
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("AEGIS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("AEGIS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    for key in ("AEGIS_MODEL", "AEGIS_API_KEY", "AEGIS_PERMISSION_MODE", "AEGIS_SERVER_PORT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(project)
    reset_engine_cache()
    yield project
    reset_engine_cache()


def test_run_cli_text_only(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MockProvider(responses=[text_response("Summary: Phase 3 test.")])

    def fake_create_provider(*args: Any, **kwargs: Any) -> MockProvider:
        return mock

    monkeypatch.setattr("aegis.cli.commands.run.create_provider", fake_create_provider)

    result = runner.invoke(app, ["run", "Summarize the README", "--workspace", str(isolated)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Phase 3 test" in result.stdout
    assert "session=" in result.stderr or "Session" in result.stderr


def test_run_cli_json_and_tool(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = tool_then_text(
        "read",
        json.dumps({"path": "README.md"}),
        "The README is about Phase 3.",
    )
    mock = MockProvider(responses=[first, second])
    monkeypatch.setattr(
        "aegis.cli.commands.run.create_provider",
        lambda *a, **k: mock,
    )

    result = runner.invoke(
        app,
        [
            "run",
            "Read README and summarize",
            "--workspace",
            str(isolated),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    # JSON mode prints payload on stdout
    data = json.loads(result.stdout)
    assert data["tool_calls"] == 1
    assert data["error"] is None
    assert "Phase 3" in data["output"] or "README" in data["output"]
    assert data["session_id"].startswith("sess_")
