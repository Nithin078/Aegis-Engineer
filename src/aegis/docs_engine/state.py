"""Persist last documentation run state."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def state_path(workspace: Path) -> Path:
    return workspace.resolve() / ".aegis" / "docs" / "state.json"


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except OSError:
        return ""
    return h.hexdigest()[:16]


def load_state(workspace: Path) -> dict[str, Any]:
    p = state_path(workspace)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(workspace: Path, report_summary: dict[str, Any], hashes: dict[str, str]) -> Path:
    p = state_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(UTC).isoformat(),
        "coverage": report_summary.get("coverage"),
        "summary": report_summary,
        "source_hashes": hashes,
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def hash_sources(workspace: Path, paths: list[str]) -> dict[str, str]:
    root = workspace.resolve()
    out: dict[str, str] = {}
    for rel in paths:
        fp = root / rel
        if fp.is_file():
            out[rel] = file_hash(fp)
    return out
