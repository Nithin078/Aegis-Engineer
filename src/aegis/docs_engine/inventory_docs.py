"""Inventory existing documentation and extract code references."""

from __future__ import annotations

import re
from pathlib import Path

# Paths and identifiers often mentioned in docs
_BACKTICK_RE = re.compile(r"`([^`\n]{1,120})`")
_PATH_RE = re.compile(r"\b(?:src/|docs/|tests/)[A-Za-z0-9_./\-]+\b")
_AEGIS_CMD_RE = re.compile(r"\baegis\s+([a-z][a-z0-9_-]*)\b", re.IGNORECASE)
_HTTP_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)")
_PACKAGE_RE = re.compile(r"\baegis\.([a-z][a-z0-9_]*)\b")


def list_doc_files(workspace: Path) -> list[Path]:
    root = workspace.resolve()
    files: list[Path] = []
    for name in ("README.md", "PHASES.md", "CHANGELOG.md"):
        p = root / name
        if p.is_file():
            files.append(p)
    docs = root / "docs"
    if docs.is_dir():
        files.extend(sorted(docs.rglob("*.md")))
    # skip proposed drafts when scanning "current" docs for coverage of real docs
    return [f for f in files if "_proposed" not in f.parts]


def extract_refs_from_text(text: str) -> set[str]:
    refs: set[str] = set()
    for m in _BACKTICK_RE.finditer(text):
        refs.add(m.group(1).strip())
    for m in _PATH_RE.finditer(text):
        refs.add(m.group(0))
    for m in _AEGIS_CMD_RE.finditer(text):
        refs.add(f"aegis {m.group(1).lower()}")
    for m in _HTTP_RE.finditer(text):
        refs.add(f"{m.group(1)} {m.group(2).rstrip(')`],.')}")
    for m in _PACKAGE_RE.finditer(text):
        refs.add(f"aegis.{m.group(1)}")
        refs.add(m.group(1))  # also bare package name under aegis
    return refs


def inventory_doc_refs(workspace: Path) -> tuple[list[Path], set[str], str]:
    """Return (files, all_refs, concatenated_lower_text)."""
    files = list_doc_files(workspace)
    all_refs: set[str] = set()
    chunks: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        chunks.append(text)
        all_refs |= extract_refs_from_text(text)
    return files, all_refs, "\n".join(chunks).lower()
