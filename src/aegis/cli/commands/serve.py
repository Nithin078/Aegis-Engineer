"""`aegis serve` — start the HTTP API server."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from aegis.config.env import load_env
from aegis.config.loader import load_config

console = Console()


def serve_command(
    host: str | None = typer.Option(None, "--host", help="Bind host"),
    port: int | None = typer.Option(None, "--port", help="Bind port"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        help="Default workspace for tools",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    reload: bool = typer.Option(False, "--reload", help="Dev auto-reload"),
) -> None:
    """Start the Starlette HTTP server (REST + SSE)."""
    load_env()
    config = load_config()
    bind_host = host or config.server.host
    bind_port = port or config.server.port

    console.print(
        f"[bold]Aegis API[/bold]  http://{bind_host}:{bind_port}/\n"
        f"  workspace: {workspace}\n"
        f"  browser:   open the URL above for a route guide\n"
        f"  health:    GET /health\n"
        f"  sessions:  POST /session  ·  POST /session/{{id}}/chat (SSE)"
    )

    import uvicorn

    from aegis.server.app import create_app

    app = create_app(workspace=workspace)
    uvicorn.run(app, host=bind_host, port=bind_port, reload=reload, log_level="info")
