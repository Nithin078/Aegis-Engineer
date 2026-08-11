"""`aegis fetch` — scrape a public URL to readable text."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from aegis.config.schema import PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry

console = Console()


def fetch_command(
    url: str = typer.Argument(..., help="HTTP/HTTPS URL to fetch and scrape"),
    max_chars: int = typer.Option(50_000, "--max-chars", min=500, max=200_000),
    include_links: bool = typer.Option(
        False, "--links", help="Include extracted hyperlinks from HTML"
    ),
    raw: bool = typer.Option(False, "--raw", help="Return raw body (truncated) not HTML text"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write result to a file"
    ),
    as_json: bool = typer.Option(False, "--json", "-j", help="JSON with metadata"),
) -> None:
    """Fetch a public web page and print scraped text (SSRF-safe)."""
    import asyncio

    eng = PermissionEngine(
        PermissionsConfig(default="allow", trust_mode="yolo", rules=[])
    )
    registry = create_default_registry(permission_engine=eng)
    ctx = ToolContext(workspace_root=Path.cwd(), agent="cli", timeout=30.0)

    async def _run() -> None:
        result = await registry.execute(
            "webfetch",
            {
                "url": url,
                "max_chars": max_chars,
                "include_links": include_links,
                "raw": raw,
            },
            ctx,
        )
        if as_json:
            typer.echo(
                json.dumps(
                    {
                        "error": result.error,
                        "title": result.title,
                        "output": result.output,
                        "metadata": result.metadata,
                    },
                    indent=2,
                )
            )
        else:
            if result.error:
                console.print(f"[red]{result.title or 'error'}[/red]")
            console.print(result.output)
        if output is not None:
            output.write_text(result.output, encoding="utf-8")
            console.print(f"[dim]Wrote {output}[/dim]")
        if result.error:
            raise typer.Exit(1)

    asyncio.run(_run())
