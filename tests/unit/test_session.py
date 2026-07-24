"""Tests for session storage and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.db.connection import init_db, reset_engine_cache
from aegis.db.migrations import CURRENT_SCHEMA_VERSION, get_schema_version
from aegis.session.manager import SessionManager, SessionNotFoundError

runner = CliRunner()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    reset_engine_cache()
    path = tmp_path / "test.db"
    init_db(path)
    yield path
    reset_engine_cache()


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    db = tmp_path / "aegis.db"
    monkeypatch.setenv("AEGIS_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("AEGIS_DB_PATH", str(db))
    for key in (
        "AEGIS_PROVIDER",
        "AEGIS_MODEL",
        "AEGIS_API_KEY",
        "AEGIS_PERMISSION_MODE",
        "AEGIS_SERVER_PORT",
        "AEGIS_LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    reset_engine_cache()
    yield db
    reset_engine_cache()


def test_init_db_creates_schema(db_path: Path) -> None:
    assert db_path.is_file()
    engine = init_db(db_path)
    assert get_schema_version(engine) == CURRENT_SCHEMA_VERSION


def test_session_crud(db_path: Path) -> None:
    manager = SessionManager(db_path)
    session = manager.create(title="Fix auth", model="gpt-4o", provider="openai")
    assert session.id.startswith("sess_")
    assert session.title == "Fix auth"

    fetched = manager.get(session.id)
    assert fetched.title == "Fix auth"

    listed = manager.list()
    assert len(listed) == 1
    assert listed[0].id == session.id

    msg = manager.add_message(session.id, "user", "Hello", tokens=10, cost_usd=0.001)
    assert msg.role == "user"
    assert msg.content == "Hello"

    messages = manager.list_messages(session.id)
    assert len(messages) == 1

    updated = manager.get(session.id)
    assert updated.token_count == 10
    assert updated.cost_usd == pytest.approx(0.001)

    export = manager.export(session.id)
    assert export["session"]["id"] == session.id
    assert len(export["messages"]) == 1

    out = db_path.parent / "export.json"
    manager.export_to_file(session.id, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["session"]["title"] == "Fix auth"

    manager.delete(session.id)
    with pytest.raises(SessionNotFoundError):
        manager.get(session.id)
    assert manager.list() == []


def test_session_not_found(db_path: Path) -> None:
    manager = SessionManager(db_path)
    with pytest.raises(SessionNotFoundError):
        manager.get("sess_missing")
    with pytest.raises(SessionNotFoundError):
        manager.delete("sess_missing")
    with pytest.raises(SessionNotFoundError):
        manager.add_message("sess_missing", "user", "hi")


def test_session_cli(isolated_env: Path) -> None:
    result = runner.invoke(app, ["session", "create", "--title", "Demo"])
    assert result.exit_code == 0
    assert "Created" in result.stdout
    session_id = result.stdout.strip().split()[1].rstrip(":")

    result = runner.invoke(app, ["session", "list", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert len(rows) == 1
    assert rows[0]["title"] == "Demo"
    session_id = rows[0]["id"]

    # Add a message via manager so show has content
    manager = SessionManager(isolated_env)
    manager.add_message(session_id, "user", "Fix the bug")

    result = runner.invoke(app, ["session", "show", session_id])
    assert result.exit_code == 0
    assert "Demo" in result.stdout
    assert "Fix the bug" in result.stdout

    out = isolated_env.parent / "out.json"
    result = runner.invoke(app, ["session", "export", session_id, "-o", str(out)])
    assert result.exit_code == 0
    assert out.is_file()

    result = runner.invoke(app, ["session", "delete", session_id, "--yes"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["session", "list"])
    assert result.exit_code == 0
    assert "No sessions" in result.stdout
