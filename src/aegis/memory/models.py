"""Memory entry models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryKind(StrEnum):
    SOLVED = "solved"
    FAILURE = "failure"
    PATTERN = "pattern"
    PREFERENCE = "preference"
    GLOBAL = "global"
    NOTE = "note"


def _new_id() -> str:
    return f"mem_{uuid4().hex[:12]}"


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=_new_id)
    kind: MemoryKind = MemoryKind.NOTE
    scope: str = "repo"  # repo | global
    repo_id: str = ""  # stable id for workspace (path hash or name)
    title: str = ""
    summary: str = ""
    issue_text: str = ""
    classification: str = ""
    files: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    score: float | None = None  # filled on query only


class MemoryQueryResult(BaseModel):
    entries: list[MemoryEntry] = Field(default_factory=list)
    query: str = ""
    repo_id: str = ""
