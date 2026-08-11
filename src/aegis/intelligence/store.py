"""Persist intelligence index under ``.aegis/intelligence/``."""

from __future__ import annotations

import json
from pathlib import Path

from aegis.intelligence.models import IntelligenceIndex


def cache_dir(root: Path) -> Path:
    return root.resolve() / ".aegis" / "intelligence"


def index_path(root: Path) -> Path:
    return cache_dir(root) / "index.json"


def save_index(root: Path, index: IntelligenceIndex) -> Path:
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        index.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path


def load_index(root: Path) -> IntelligenceIndex | None:
    path = index_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return IntelligenceIndex.model_validate(data)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
