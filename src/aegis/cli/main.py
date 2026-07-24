"""CLI entry point for Aegis Engineer."""

from __future__ import annotations

import typer

from aegis import __version__
from aegis.cli.commands.config import app as config_app
from aegis.cli.commands.doctor import doctor
from aegis.cli.commands.session import app as session_app
from aegis.cli.commands.version import version_command

app = typer.Typer(
    name="aegis",
    help="Aegis Engineer — autonomous software engineering with repository intelligence.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aegis {__version__}")
        raise typer.Exit()


@app.callback()
def main(
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
) -> None:
    """Aegis Engineer CLI."""
    # Verbose flag is accepted globally; wiring to logging lands in a later phase.
    _ = verbose


app.command("version")(version_command)
app.command("doctor")(doctor)
app.add_typer(config_app, name="config")
app.add_typer(session_app, name="session")


if __name__ == "__main__":
    app()
