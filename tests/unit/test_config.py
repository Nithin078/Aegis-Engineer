"""Tests for configuration loading and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.config.loader import (
    get_db_path,
    load_config,
    set_config_value,
    unset_config_value,
)
from aegis.config.schema import AegisConfig, set_nested, unset_nested

runner = CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AEGIS_CONFIG_DIR at a temp directory and clear related env."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(config_dir))
    for key in (
        "AEGIS_PROVIDER",
        "AEGIS_MODEL",
        "AEGIS_API_KEY",
        "AEGIS_PERMISSION_MODE",
        "AEGIS_SERVER_PORT",
        "AEGIS_LOG_LEVEL",
        "AEGIS_DB_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    # Isolate from real project config in the workspace.
    monkeypatch.chdir(project_dir)
    return config_dir

def test_default_config_loads(isolated_config: Path) -> None:
    config = load_config()
    assert config.provider.default == "anthropic"
    assert config.server.port == 4096
    assert config.permissions.trust_mode == "interactive"


def test_user_config_overrides_defaults(isolated_config: Path) -> None:
    user_file = isolated_config / "config.json"
    user_file.write_text(
        json.dumps({"provider": {"default": "openai", "model": "gpt-4o"}}),
        encoding="utf-8",
    )
    config = load_config()
    assert config.provider.default == "openai"
    assert config.provider.model == "gpt-4o"
    # Untouched defaults remain
    assert config.server.port == 4096


def test_project_config_overrides_user(isolated_config: Path, tmp_path: Path) -> None:
    user_file = isolated_config / "config.json"
    user_file.write_text(
        json.dumps({"provider": {"default": "openai", "model": "gpt-4o"}}),
        encoding="utf-8",
    )
    project_cfg = tmp_path / "project" / ".aegis" / "config.json"
    project_cfg.parent.mkdir(parents=True)
    project_cfg.write_text(
        json.dumps({"provider": {"model": "gpt-4o-mini"}, "server": {"port": 5000}}),
        encoding="utf-8",
    )
    config = load_config(project_dir=tmp_path / "project")
    assert config.provider.default == "openai"  # from user
    assert config.provider.model == "gpt-4o-mini"  # project wins
    assert config.server.port == 5000


def test_env_overrides_project(
    isolated_config: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_cfg = tmp_path / "project" / ".aegis.json"
    project_cfg.write_text(
        json.dumps({"provider": {"default": "openai"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("AEGIS_PROVIDER", "ollama")
    monkeypatch.setenv("AEGIS_SERVER_PORT", "9999")
    config = load_config(project_dir=tmp_path / "project")
    assert config.provider.default == "ollama"
    assert config.server.port == 9999


def test_set_and_unset_config_value(isolated_config: Path) -> None:
    path = set_config_value("provider.model", "claude-test")
    assert path == isolated_config / "config.json"
    config = load_config()
    assert config.provider.model == "claude-test"

    path2, removed = unset_config_value("provider.model")
    assert removed is True
    assert path2 == path
    # After unset, default model returns
    config2 = load_config()
    assert config2.provider.model == AegisConfig().provider.model


def test_set_project_config(isolated_config: Path, tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    path = set_config_value("server.port", 4321, project=True, project_dir=project_dir)
    assert path == project_dir / ".aegis" / "config.json"
    config = load_config(project_dir=project_dir)
    assert config.server.port == 4321


def test_db_path_resolution(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    default_path = get_db_path()
    assert default_path == isolated_config / "aegis.db"

    custom = tmp_path / "custom.db"
    monkeypatch.setenv("AEGIS_DB_PATH", str(custom))
    assert get_db_path() == custom.resolve()


def test_nested_helpers() -> None:
    data: dict = {}
    set_nested(data, "a.b.c", 1)
    assert data == {"a": {"b": {"c": 1}}}
    assert unset_nested(data, "a.b.c") is True
    assert data == {}
    assert unset_nested(data, "missing.key") is False


def test_config_cli_list_and_set(isolated_config: Path) -> None:
    result = runner.invoke(app, ["config", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["provider"]["default"] == "anthropic"

    result = runner.invoke(app, ["config", "set", "provider.default", "google"])
    assert result.exit_code == 0
    assert "Set" in result.stdout

    result = runner.invoke(app, ["config", "list", "--json"])
    assert json.loads(result.stdout)["provider"]["default"] == "google"

    result = runner.invoke(app, ["config", "unset", "provider.default"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert "User config" in result.stdout
