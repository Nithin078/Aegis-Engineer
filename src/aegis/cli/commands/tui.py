"""`aegis tui` — launch the terminal UI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console(stderr=True)


def tui_command(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        help="Workspace root for tools",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Override model"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Override provider"),
    trust_mode: str | None = typer.Option(
        None,
        "--trust-mode",
        help="interactive | yolo | readonly | ci (default: interactive)",
    ),
    server: str | None = typer.Option(
        None,
        "--server",
        help="Connect to running aegis serve URL (e.g. http://127.0.0.1:4096)",
    ),
) -> None:
    """Launch the interactive Textual chat UI."""
    from aegis.tui.app import run_tui

    try:
        run_tui(
            workspace=workspace,
            model=model,
            provider=provider,
            trust_mode=trust_mode,
            server_url=server,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Bye.[/dim]")
        raise typer.Exit(0) from None
