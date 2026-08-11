"""Phase 10: memory store, query, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.memory.models import MemoryEntry, MemoryKind
from aegis.memory.store import MemoryStore, repo_id_for

runner = CliRunner()


def test_repo_id_stable(tmp_path: Path) -> None:
    a = repo_id_for(tmp_path)
    b = repo_id_for(tmp_path)
    assert a == b
    assert "-" in a


def test_record_solved_and_query(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.record_solved(
        issue_text="add() subtracts instead of adds in math_ops",
        summary="Fix add operator to use plus",
        classification="bug",
        files=["calc/math_ops.py"],
        plan_summary="Change - to +",
        code_summary="return a + b",
        tags=["bug", "math"],
    )
    store.record_failure(
        issue_text="auth token expires too soon",
        approach="hardcoded sleep",
        reason="tests still flaky",
        files=["auth.py"],
        classification="bug",
    )
    entries = store.list_entries()
    assert len(entries) >= 2
    hits = store.query("math add operator subtraction", limit=3)
    assert hits.entries
    assert hits.entries[0].kind == MemoryKind.SOLVED
    assert (hits.entries[0].score or 0) > 0


def test_forget_and_export_import(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    e = store.add(
        MemoryEntry(kind=MemoryKind.NOTE, title="pref", summary="use pytest", tags=["pref"])
    )
    assert store.get(e.id) is not None
    data = store.export_all()
    assert len(data["entries"]) >= 1
    n = store.forget(entry_id=e.id)
    assert n == 1
    assert store.get(e.id) is None

    out = tmp_path / "export.json"
    out.write_text(json.dumps(data), encoding="utf-8")
    # re-import into fresh store path
    store2 = MemoryStore(tmp_path / "other")
    (tmp_path / "other").mkdir()
    imported = store2.import_entries(json.loads(out.read_text(encoding="utf-8")))
    assert imported >= 1


def test_format_for_prompt(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.record_solved(
        issue_text="broken login",
        summary="Fixed session cookie flags",
        classification="bug",
        files=["auth/session.py"],
    )
    result = store.query("login session cookie", limit=2)
    text = store.format_for_prompt(result)
    assert "session" in text.lower() or "cookie" in text.lower() or "Fixed" in text


def test_cli_memory_list_add(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "memory",
            "add",
            "--title",
            "Use dataclasses",
            "--summary",
            "project prefers dataclasses",
            "-w",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.stdout
    r2 = runner.invoke(app, ["memory", "list", "-w", str(tmp_path)])
    assert r2.exit_code == 0
    assert "dataclasses" in r2.stdout or "Use dataclasses" in r2.stdout


def test_cli_memory_help() -> None:
    r = runner.invoke(app, ["memory", "--help"])
    assert r.exit_code == 0
    assert "list" in r.stdout
