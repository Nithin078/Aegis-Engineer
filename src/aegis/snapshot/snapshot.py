"""Track workspace file contents and restore on demand."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSnapshot:
    path: str  # relative posix path
    content: bytes | None  # None = did not exist
    digest: str = ""

    def __post_init__(self) -> None:
        if self.content is not None and not self.digest:
            self.digest = hashlib.sha256(self.content).hexdigest()[:16]


@dataclass
class SnapshotSession:
    """
    Capture selected files (or whole tree of text-ish files) before edits.

    On revert, restore original content and delete newly created files that
    were tracked as missing at snapshot time.
    """

    root: Path
    files: dict[str, FileSnapshot] = field(default_factory=dict)

    @classmethod
    def capture(
        cls,
        root: Path | str,
        paths: list[str] | None = None,
        *,
        patterns: tuple[str, ...] = ("**/*.py", "**/*.toml", "**/*.md", "**/*.txt"),
        max_files: int = 500,
        max_bytes: int = 2_000_000,
    ) -> SnapshotSession:
        root_p = Path(root).resolve()
        session = cls(root=root_p)
        rels: list[str] = []
        if paths:
            rels = [p.replace("\\", "/") for p in paths]
        else:
            seen: set[str] = set()
            for pat in patterns:
                for p in root_p.glob(pat):
                    if not p.is_file():
                        continue
                    if any(part.startswith(".") for part in p.relative_to(root_p).parts):
                        # skip .git / .aegis / .venv etc.
                        if p.relative_to(root_p).parts[0].startswith("."):
                            continue
                    rel = p.relative_to(root_p).as_posix()
                    if rel not in seen:
                        seen.add(rel)
                        rels.append(rel)
                    if len(rels) >= max_files:
                        break
                if len(rels) >= max_files:
                    break

        for rel in rels:
            abs_path = root_p / rel
            if abs_path.is_file():
                data = abs_path.read_bytes()
                if len(data) > max_bytes:
                    continue
                session.files[rel] = FileSnapshot(path=rel, content=data)
            else:
                session.files[rel] = FileSnapshot(path=rel, content=None)
        return session

    def remember(self, relative: str) -> None:
        """Ensure a path is tracked (call before creating/editing)."""
        rel = relative.replace("\\", "/")
        if rel in self.files:
            return
        abs_path = self.root / rel
        if abs_path.is_file():
            self.files[rel] = FileSnapshot(path=rel, content=abs_path.read_bytes())
        else:
            self.files[rel] = FileSnapshot(path=rel, content=None)

    def changed_files(self) -> list[str]:
        changed: list[str] = []
        for rel, snap in self.files.items():
            abs_path = self.root / rel
            if snap.content is None:
                if abs_path.is_file():
                    changed.append(rel)
                continue
            if not abs_path.is_file():
                changed.append(rel)
                continue
            if abs_path.read_bytes() != snap.content:
                changed.append(rel)
        return changed

    def revert(self) -> list[str]:
        """Restore all tracked files; return list of paths touched."""
        touched: list[str] = []
        for rel, snap in self.files.items():
            abs_path = self.root / rel
            if snap.content is None:
                if abs_path.is_file():
                    abs_path.unlink()
                    touched.append(rel)
                    # prune empty parents (best-effort)
                    parent = abs_path.parent
                    while parent != self.root and parent.is_dir():
                        try:
                            parent.rmdir()
                        except OSError:
                            break
                        parent = parent.parent
            else:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                if not abs_path.is_file() or abs_path.read_bytes() != snap.content:
                    abs_path.write_bytes(snap.content)
                    touched.append(rel)
        return touched

    def export_backup(self, dest: Path | str) -> Path:
        """Write a full copy of snapshotted content for inspection."""
        dest_p = Path(dest)
        dest_p.mkdir(parents=True, exist_ok=True)
        for rel, snap in self.files.items():
            if snap.content is None:
                continue
            out = dest_p / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(snap.content)
        return dest_p

    def diff_summary(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for rel in self.changed_files():
            snap = self.files[rel]
            abs_path = self.root / rel
            if snap.content is None and abs_path.is_file():
                kind = "created"
            elif snap.content is not None and not abs_path.is_file():
                kind = "deleted"
            else:
                kind = "modified"
            rows.append({"path": rel, "change": kind})
        return rows


def copy_tree_snapshot(src: Path | str, dest: Path | str) -> Path:
    """Full directory copy (excluding common junk) for offline isolation."""
    src_p = Path(src).resolve()
    dest_p = Path(dest).resolve()
    if dest_p.exists():
        shutil.rmtree(dest_p)
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".aegis",
        "node_modules",
        "*.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    )
    shutil.copytree(src_p, dest_p, ignore=ignore)
    return dest_p
