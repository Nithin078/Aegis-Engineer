"""Git worktree creation and cleanup for isolated solve runs."""

from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class WorktreeError(RuntimeError):
    """Raised when worktree operations fail."""


def _run_git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if check and proc.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )
    return proc


def is_git_repo(path: Path | str) -> bool:
    root = Path(path).resolve()
    try:
        proc = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=root, check=False)
        return proc.returncode == 0 and (proc.stdout or "").strip() == "true"
    except (OSError, WorktreeError, subprocess.TimeoutExpired):
        return False


def repo_root(path: Path | str) -> Path:
    root = Path(path).resolve()
    proc = _run_git(["rev-parse", "--show-toplevel"], cwd=root)
    return Path((proc.stdout or "").strip())


def sanitize_branch_name(text: str, *, prefix: str = "aegis") -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")[:40] or "change"
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{prefix}/{slug}-{stamp}-{short}"


@dataclass
class WorktreeSession:
    """An active worktree bound to a temporary branch."""

    repo: Path
    path: Path
    branch: str
    base_ref: str
    created: bool = True

    def status_porcelain(self) -> str:
        proc = _run_git(["status", "--porcelain"], cwd=self.path, check=False)
        return (proc.stdout or "").strip()

    def changed_files(self) -> list[str]:
        proc = _run_git(["diff", "--name-only", self.base_ref], cwd=self.path, check=False)
        files = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        # include untracked
        porcelain = self.status_porcelain()
        for line in porcelain.splitlines():
            if line.startswith("??"):
                files.append(line[3:].strip())
        # unique preserve order
        seen: set[str] = set()
        out: list[str] = []
        for f in files:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

    def add_all(self) -> None:
        _run_git(["add", "-A"], cwd=self.path)

    def commit(self, message: str) -> str | None:
        """Commit staged+tracked changes; return sha or None if nothing to commit."""
        self.add_all()
        # nothing?
        status = self.status_porcelain()
        if not status:
            # also check staged via diff
            proc = _run_git(["diff", "--cached", "--quiet"], cwd=self.path, check=False)
            if proc.returncode == 0:
                return None
        _run_git(["commit", "-m", message], cwd=self.path)
        sha = _run_git(["rev-parse", "HEAD"], cwd=self.path)
        return (sha.stdout or "").strip() or None

    def cleanup(self, *, delete_branch: bool = True) -> None:
        """Remove worktree directory and optionally the branch."""
        try:
            _run_git(
                ["worktree", "remove", "--force", str(self.path)],
                cwd=self.repo,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        # prune metadata
        try:
            _run_git(["worktree", "prune"], cwd=self.repo, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if delete_branch:
            try:
                _run_git(["branch", "-D", self.branch], cwd=self.repo, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def __enter__(self) -> WorktreeSession:
        return self

    def __exit__(self, *exc: object) -> None:
        self.cleanup()


def create_worktree(
    workspace: Path | str,
    *,
    branch_name: str | None = None,
    base_ref: str = "HEAD",
    path: Path | str | None = None,
) -> WorktreeSession:
    """
    Create a new git worktree on a fresh branch for isolated edits.

    Worktrees are placed under `<repo>/.aegis/worktrees/<branch-slug>` by default.
    """
    root = repo_root(workspace)
    if not is_git_repo(root):
        raise WorktreeError(f"Not a git repository: {workspace}")

    branch = branch_name or sanitize_branch_name("solve")
    if path is None:
        slug = branch.replace("/", "-")
        dest = root / ".aegis" / "worktrees" / slug
    else:
        dest = Path(path).resolve()

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Ensure base_ref exists
    _run_git(["rev-parse", "--verify", base_ref], cwd=root)

    _run_git(
        ["worktree", "add", "-b", branch, str(dest), base_ref],
        cwd=root,
    )
    return WorktreeSession(repo=root, path=dest, branch=branch, base_ref=base_ref)
