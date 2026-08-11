"""Phase 9: snapshot + git worktree isolation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aegis.snapshot.snapshot import SnapshotSession, copy_tree_snapshot
from aegis.worktree.worktree import (
    WorktreeError,
    create_worktree,
    is_git_repo,
    sanitize_branch_name,
)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "aegis@test.local"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Aegis Test"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def test_snapshot_revert(tmp_path: Path) -> None:
    root = tmp_path / "snap"
    root.mkdir()
    f = root / "a.py"
    f.write_text("original\n", encoding="utf-8")
    session = SnapshotSession.capture(root, paths=["a.py", "new.py"])
    f.write_text("changed\n", encoding="utf-8")
    (root / "new.py").write_text("created\n", encoding="utf-8")
    assert set(session.changed_files()) >= {"a.py", "new.py"}
    touched = session.revert()
    assert "a.py" in touched
    assert f.read_text(encoding="utf-8") == "original\n"
    assert not (root / "new.py").exists()


def test_copy_tree_snapshot(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    (src / "x.py").write_text("1\n", encoding="utf-8")
    (src / ".venv").mkdir()
    (src / ".venv" / "junk").write_text("nope", encoding="utf-8")
    copy_tree_snapshot(src, dest)
    assert (dest / "x.py").is_file()
    assert not (dest / ".venv").exists()


def test_sanitize_branch_name() -> None:
    name = sanitize_branch_name("Fix Auth!! Bug")
    assert name.startswith("aegis/")
    assert " " not in name
    assert "!" not in name


def test_worktree_create_edit_cleanup(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git_init(root)
    assert is_git_repo(root)

    session = create_worktree(root, branch_name="aegis/test-branch")
    try:
        assert session.path.is_dir()
        assert session.branch == "aegis/test-branch"
        target = session.path / "app.py"
        target.write_text("x = 2\n", encoding="utf-8")
        changed = session.changed_files()
        assert "app.py" in changed
        # original tree untouched
        assert (root / "app.py").read_text(encoding="utf-8") == "x = 1\n"
        sha = session.commit("test change")
        assert sha
    finally:
        session.cleanup()
    assert not session.path.exists()


def test_worktree_non_git_raises(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "f.txt").write_text("x", encoding="utf-8")
    with pytest.raises(WorktreeError):
        create_worktree(plain)
