"""Tests for .env loading."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aegis.config.env import load_env, reset_env_loader


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_env_loader()
    # Avoid leaking real project .env into these tests via cwd.
    yield
    reset_env_loader()


def test_load_project_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("AEGIS_MODEL", raising=False)
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=from-dotenv\n"
        "OPENAI_BASE_URL=https://api.groq.com/openai/v1\n"
        "AEGIS_MODEL=llama-test\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    # Point user config dir away so only project .env loads
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(tmp_path / "no-user-config"))

    loaded = load_env(project_dir=tmp_path, force=True)
    assert any(p.name == ".env" for p in loaded)
    assert os.environ.get("OPENAI_API_KEY") == "from-dotenv"
    assert os.environ.get("OPENAI_BASE_URL") == "https://api.groq.com/openai/v1"
    assert os.environ.get("AEGIS_MODEL") == "llama-test"


def test_global_user_env_used_when_no_project_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    user_dir = tmp_path / "user-config"
    user_dir.mkdir()
    (user_dir / ".env").write_text(
        "OPENAI_API_KEY=global-key\nOPENAI_BASE_URL=https://api.groq.com/openai/v1\n",
        encoding="utf-8",
    )
    project = tmp_path / "other-project"
    project.mkdir()
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(user_dir))
    monkeypatch.chdir(project)

    load_env(project_dir=project, force=True)
    assert os.environ.get("OPENAI_API_KEY") == "global-key"
    assert os.environ.get("OPENAI_BASE_URL") == "https://api.groq.com/openai/v1"


def test_shell_env_wins_over_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(tmp_path / "no-user-config"))

    load_env(project_dir=tmp_path, force=True)
    assert os.environ.get("OPENAI_API_KEY") == "from-shell"
