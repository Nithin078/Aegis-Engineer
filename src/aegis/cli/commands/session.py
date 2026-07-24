"""`aegis session` commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.config.loader import get_db_path, load_config
from aegis.session.manager import SessionManager, SessionNotFoundError

console = Console()

app = typer.Typer(
    name="session",
    help="Manage conversation sessions.",
    no_args_is_help=True,
)


def _manager() -> SessionManager:
    config = load_config()
    return SessionManager(get_db_path(config))


@app.command("list")
def session_list(
    limit: int = typer.Option(50, "--limit", "-n", help="Max sessions to show"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List sessions (most recently updated first)."""
    manager = _manager()
    sessions = manager.list(limit=limit)
    if as_json:
        payload = [
            {
                "id": s.id,
                "title": s.title,
                "model": s.model,
                "provider": s.provider,
                "token_count": s.token_count,
                "cost_usd": s.cost_usd,
                "status": s.status,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    if not sessions:
        console.print("No sessions found.")
        return

    table = Table(title="Sessions", show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Tokens")
    table.add_column("Cost USD")
    table.add_column("Status")
    for s in sessions:
        table.add_row(
            s.id,
            s.title,
            s.provider or "-",
            s.model or "-",
            str(s.token_count),
            f"{s.cost_usd:.4f}",
            s.status,
        )
    console.print(table)


@app.command("show")
def session_show(
    session_id: str = typer.Argument(..., help="Session ID"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show session details and messages."""
    manager = _manager()
    try:
        data = manager.export(session_id)
    except SessionNotFoundError:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(code=1) from None

    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
        return

    session = data["session"]
    console.print(f"[bold]{session['title']}[/bold] ({session['id']})")
    provider = session.get("provider") or "-"
    model = session.get("model") or "-"
    console.print(f"Provider: {provider}  Model: {model}")
    console.print(
        f"Tokens: {session.get('token_count', 0)}  "
        f"Cost: ${session.get('cost_usd', 0):.4f}  "
        f"Status: {session.get('status')}"
    )
    console.print(f"Created: {session.get('created_at')}  Updated: {session.get('updated_at')}")
    messages = data["messages"]
    console.print(f"\n[bold]Messages ({len(messages)})[/bold]")
    for msg in messages:
        role = msg["role"]
        content = msg["content"] or ""
        preview = content if len(content) <= 120 else content[:117] + "..."
        console.print(f"  [{role}] {preview}")


@app.command("create")
def session_create(
    title: str = typer.Option("Untitled session", "--title", "-t", help="Session title"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model name"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Provider name"),
) -> None:
    """Create a new empty session."""
    config = load_config()
    manager = SessionManager(get_db_path(config))
    session = manager.create(
        title=title,
        model=model or config.provider.model,
        provider=provider or config.provider.default,
    )
    console.print(f"[green]Created[/green] {session.id}: {session.title}")


@app.command("delete")
def session_delete(
    session_id: str = typer.Argument(..., help="Session ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a session and its messages."""
    if not yes:
        confirmed = typer.confirm(f"Delete session {session_id}?")
        if not confirmed:
            raise typer.Abort()
    manager = _manager()
    try:
        manager.delete(session_id)
    except SessionNotFoundError:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(code=1) from None
    console.print(f"[green]Deleted[/green] {session_id}")


@app.command("export")
def session_export(
    session_id: str = typer.Argument(..., help="Session ID"),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output JSON file path",
        dir_okay=False,
        writable=True,
    ),
) -> None:
    """Export a session and its messages as JSON."""
    manager = _manager()
    try:
        path = manager.export_to_file(session_id, output)
    except SessionNotFoundError:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(code=1) from None
    console.print(f"[green]Exported[/green] {session_id} → {path}")
