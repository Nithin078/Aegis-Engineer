"""Starlette application factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route

from aegis.config.loader import get_db_path, load_config, load_env

# Re-export for older imports
from aegis.server.deps import get_state as get_state  # noqa: F401
from aegis.server.routes import chat, events, health, providers, sessions, tools
from aegis.server.routes import root as root_routes
from aegis.server.state import AppState, ProviderFactory
from aegis.session.manager import SessionManager


def create_app(
    *,
    config: Any | None = None,
    db_path: Path | str | None = None,
    workspace: Path | str | None = None,
    provider_factory: ProviderFactory | None = None,
    cors_origins: list[str] | None = None,
) -> Starlette:
    """Build the ASGI app.

    Parameters are optional so production uses config defaults; tests inject
    db_path / provider_factory for isolation.
    """
    load_env()
    cfg = config or load_config()
    path = Path(db_path) if db_path else get_db_path(cfg)
    workspace_root = Path(workspace) if workspace else Path.cwd()
    origins = cors_origins if cors_origins is not None else list(cfg.server.cors_origins)

    state = AppState(
        config=cfg,
        sessions=SessionManager(path),
        workspace=workspace_root.resolve(),
        provider_factory=provider_factory,
    )

    routes = [
        Route("/", root_routes.root, methods=["GET"]),
        Route("/health", health.health, methods=["GET"]),
        Route("/session", sessions.create_session, methods=["POST"]),
        Route("/session/{session_id}", sessions.get_session, methods=["GET"]),
        Route(
            "/session/{session_id}/messages",
            sessions.list_messages,
            methods=["GET"],
        ),
        Route(
            "/session/{session_id}/chat",
            chat.chat_session,
            methods=["POST"],
        ),
        Route("/tool/execute", tools.execute_tool, methods=["POST"]),
        Route("/provider", providers.list_providers, methods=["GET"]),
        Route("/events", events.event_stream, methods=["GET"]),
    ]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=origins or ["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ]

    # DB schema is ensured when SessionManager is constructed above.
    app = Starlette(routes=routes, middleware=middleware)
    app.state.aegis = state  # type: ignore[attr-defined]
    return app
