"""Session REST routes."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from aegis.server.deps import get_state
from aegis.session.manager import SessionNotFoundError


def _session_dict(session: Any, message_count: int | None = None) -> dict[str, Any]:
    data = {
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
    if message_count is not None:
        data["message_count"] = message_count
    return data


async def create_session(request: Request) -> JSONResponse:
    state = get_state(request)
    body: dict[str, Any] = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()

    config = state.config
    session = state.sessions.create(
        title=body.get("title") or "Untitled session",
        model=body.get("model") or config.provider.model,
        provider=body.get("provider") or config.provider.default,
    )
    return JSONResponse(_session_dict(session), status_code=201)


async def get_session(request: Request) -> JSONResponse:
    state = get_state(request)
    session_id = request.path_params["session_id"]
    try:
        session = state.sessions.get(session_id)
        messages = state.sessions.list_messages(session_id)
    except SessionNotFoundError:
        return JSONResponse({"error": "session not found"}, status_code=404)
    return JSONResponse(_session_dict(session, message_count=len(messages)))


async def list_messages(request: Request) -> JSONResponse:
    state = get_state(request)
    session_id = request.path_params["session_id"]
    try:
        messages = state.sessions.list_messages(session_id)
    except SessionNotFoundError:
        return JSONResponse({"error": "session not found"}, status_code=404)

    payload = [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "tool_calls": m.tool_calls,
            "tool_result": m.tool_result,
            "tokens": m.tokens,
            "cost_usd": m.cost_usd,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
    return JSONResponse({"messages": payload})
