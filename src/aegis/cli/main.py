"""CLI entry point for Aegis Engineer."""

from __future__ import annotations

from pathlib import Path

import typer

from aegis import __version__
from aegis.cli.commands.benchmark_cmd import app as benchmark_app
from aegis.cli.commands.config import app as config_app
from aegis.cli.commands.doctor import doctor
from aegis.cli.commands.document import document_command
from aegis.cli.commands.intelligence import app as intelligence_app
from aegis.cli.commands.memory_cmd import app as memory_app
from aegis.cli.commands.observe import app as observe_app
from aegis.cli.commands.push import push_command
from aegis.cli.commands.run import run_command
from aegis.cli.commands.serve import serve_command
from aegis.cli.commands.session import app as session_app
from aegis.cli.commands.solve import solve_command
from aegis.cli.commands.test_cmd import app as test_app
from aegis.cli.commands.tui import tui_command
from aegis.cli.commands.version import version_command
from aegis.config.env import load_env

# Load project .env + global ~/.config/aegis/.env (shell env still wins).
load_env()

app = typer.Typer(
    name="aegis",
    help="Aegis Engineer — autonomous software engineering with repository intelligence.",
    no_args_is_help=False,
    add_completion=False,
    invoke_without_command=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aegis {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace for default TUI launch (when no subcommand).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Aegis Engineer CLI. With no subcommand, launches the TUI."""
    _ = verbose
    if ctx.invoked_subcommand is None:
        from aegis.tui.app import run_tui

        run_tui(workspace=workspace or Path.cwd())


app.command("version")(version_command)
app.command("doctor")(doctor)
app.command("run")(run_command)
app.command("serve")(serve_command)
app.command("tui")(tui_command)
app.command("push")(push_command)
app.command("document")(document_command)
app.command("solve")(solve_command)
app.add_typer(intelligence_app, name="intelligence")
app.add_typer(memory_app, name="memory")
app.add_typer(observe_app, name="observe")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(test_app, name="test")
app.add_typer(config_app, name="config")
app.add_typer(session_app, name="session")


if __name__ == "__main__":
    app()
