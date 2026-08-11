"""Request helpers."""

from __future__ import annotations

from starlette.requests import Request

from aegis.server.state import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.aegis  # type: ignore[no-any-return]
