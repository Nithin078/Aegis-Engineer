"""`aegis config` commands."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from aegis.config.loader import load_config, set_config_value, unset_config_value

console = Console()

app = typer.Typer(
    name="config",
    help="Manage configuration, providers, and settings.",
    no_args_is_help=True,
)


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


@app.command("list")
def config_list(
    as_json: bool = typer.Option(False, "--json", "-j", help="Output as JSON."),
) -> None:
    """Show effective configuration (defaults + user + project + env)."""
    config = load_config()
    if as_json:
        typer.echo(json.dumps(config.model_dump(mode="json"), indent=2))
        return

    flat = config.to_flat_dict()
    table = Table(title="Aegis Config", show_header=True, header_style="bold")
    table.add_column("Key")
    table.add_column("Value")
    for key in sorted(flat.keys()):
        table.add_row(key, _format_value(flat[key]))
    console.print(table)


@app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Dotted config key, e.g. provider.model"),
    value: str = typer.Argument(..., help="Value to set"),
    project: bool = typer.Option(
        False,
        "--project",
        help="Write to project .aegis/config.json instead of user config.",
    ),
) -> None:
    """Set a configuration value."""
    try:
        path = set_config_value(key, value, project=project)
    except Exception as exc:
        console.print(f"[red]Failed to set {key}: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Set[/green] {key} = {value}")
    console.print(f"Wrote {path}")


@app.command("unset")
def config_unset(
    key: str = typer.Argument(..., help="Dotted config key to remove"),
    project: bool = typer.Option(
        False,
        "--project",
        help="Remove from project .aegis/config.json instead of user config.",
    ),
) -> None:
    """Remove a configuration value from the target config file."""
    path, removed = unset_config_value(key, project=project)
    if not removed:
        console.print(f"[yellow]Key not found in {path}: {key}[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]Unset[/green] {key}")
    console.print(f"Updated {path}")


@app.command("path")
def config_path() -> None:
    """Show config and database paths."""
    from aegis.config.loader import get_db_path, get_user_config_path

    console.print(f"User config: {get_user_config_path()}")
    console.print(f"Database:    {get_db_path()}")
