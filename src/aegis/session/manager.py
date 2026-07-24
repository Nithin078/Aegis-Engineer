"""Session CRUD operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import col, select

from aegis.db.connection import get_engine, get_session
from aegis.db.models import Message, Session


class SessionNotFoundError(LookupError):
    """Raised when a session id does not exist."""


class SessionManager:
    """Create, read, update, delete, and export conversation sessions."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        # Ensure schema exists.
        get_engine(self.db_path)

    def create(
        self,
        title: str = "Untitled session",
        *,
        model: str | None = None,
        provider: str | None = None,
    ) -> Session:
        session = Session(title=title, model=model, provider=provider)
        with get_session(self.db_path) as db:
            db.add(session)
            db.commit()
            db.refresh(session)
            db.expunge(session)
        return session

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Session]:
        with get_session(self.db_path) as db:
            statement = (
                select(Session)
                .order_by(col(Session.updated_at).desc())
                .offset(offset)
                .limit(limit)
            )
            rows = list(db.exec(statement).all())
            for row in rows:
                db.expunge(row)
            return rows

    def get(self, session_id: str) -> Session:
        with get_session(self.db_path) as db:
            row = db.get(Session, session_id)
            if row is None:
                raise SessionNotFoundError(session_id)
            db.expunge(row)
            return row

    def delete(self, session_id: str) -> None:
        with get_session(self.db_path) as db:
            row = db.get(Session, session_id)
            if row is None:
                raise SessionNotFoundError(session_id)
            # Delete messages first (SQLite may not enforce CASCADE without PRAGMA).
            messages = db.exec(select(Message).where(Message.session_id == session_id)).all()
            for msg in messages:
                db.delete(msg)
            db.delete(row)
            db.commit()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_result: dict[str, Any] | None = None,
        tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> Message:
        with get_session(self.db_path) as db:
            session = db.get(Session, session_id)
            if session is None:
                raise SessionNotFoundError(session_id)

            message = Message(
                session_id=session_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_result=tool_result,
                tokens=tokens,
                cost_usd=cost_usd,
            )
            session.updated_at = datetime.now(UTC)
            if tokens:
                session.token_count += tokens
            if cost_usd:
                session.cost_usd += cost_usd

            db.add(message)
            db.add(session)
            db.commit()
            db.refresh(message)
            db.expunge(message)
            return message

    def list_messages(self, session_id: str) -> list[Message]:
        with get_session(self.db_path) as db:
            if db.get(Session, session_id) is None:
                raise SessionNotFoundError(session_id)
            statement = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(col(Message.created_at).asc())
            )
            rows = list(db.exec(statement).all())
            for row in rows:
                db.expunge(row)
            return rows

    def export(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        messages = self.list_messages(session_id)
        return {
            "session": _session_to_dict(session),
            "messages": [_message_to_dict(m) for m in messages],
        }

    def export_to_file(self, session_id: str, path: Path | str) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = self.export(session_id)
        out.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        return out


def _session_to_dict(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "model": session.model,
        "provider": session.provider,
        "token_count": session.token_count,
        "cost_usd": session.cost_usd,
        "status": session.status,
    }


def _message_to_dict(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "tool_calls": message.tool_calls,
        "tool_result": message.tool_result,
        "tokens": message.tokens,
        "cost_usd": message.cost_usd,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }
