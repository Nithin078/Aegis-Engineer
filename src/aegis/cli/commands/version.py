"""`aegis version` command."""

from __future__ import annotations

import json
import platform
import sys

import typer

from aegis import __version__


def version_command(
    as_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output version information as JSON.",
    ),
) -> None:
    """Show version information."""
    info = {
        "name": "aegis-engineer",
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }

    if as_json:
        typer.echo(json.dumps(info, indent=2))
    else:
        typer.echo(f"aegis-engineer {__version__}")
        typer.echo(f"Python {info['python']}")
        typer.echo(f"Platform {info['platform']}")
