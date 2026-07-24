"""SQLModel table definitions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, Text
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=lambda: _new_id("sess"), primary_key=True)
    title: str = Field(default="Untitled session")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    model: str | None = Field(default=None)
    provider: str | None = Field(default=None)
    token_count: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    status: str = Field(default="active")  # active | complete | failed


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(default_factory=lambda: _new_id("msg"), primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    role: str = Field(sa_column=Column(Text, nullable=False))
    content: str = Field(default="", sa_column=Column(Text, nullable=False))
    tool_calls: list[dict[str, Any]] | None = Field(default=None, sa_type=JSON)
    tool_result: dict[str, Any] | None = Field(default=None, sa_type=JSON)
    tokens: int | None = Field(default=None)
    cost_usd: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


class SchemaMeta(SQLModel, table=True):
    """Tracks applied schema version for simple migrations."""

    __tablename__ = "schema_meta"

    key: str = Field(primary_key=True)
    value: str = Field(default="")
