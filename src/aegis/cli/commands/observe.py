"""`aegis observe` — session traces, cost, latency, reasoning."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.observability.store import list_traces, load_trace, render_summary_md

console = Console()

app = typer.Typer(
    name="observe",
    help="Inspect solve/run observability traces (cost, tools, reasoning).",
    no_args_is_help=True,
)


@app.command("list")
def observe_list(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    limit: int = typer.Option(20, "--limit", "-n"),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """List recent traces under .aegis/traces/."""
    rows = list_traces(workspace, limit=limit)
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        console.print("[dim]No traces yet. Run `aegis solve` to create one.[/dim]")
        return
    table = Table(title="Traces")
    table.add_column("ID")
    table.add_column("Workflow")
    table.add_column("OK")
    table.add_column("Tokens")
    table.add_column("Cost")
    table.add_column("ms")
    for r in rows:
        totals = r.get("totals") or {}
        table.add_row(
            str(r.get("id") or ""),
            str(r.get("workflow") or ""),
            str(r.get("success")),
            str(totals.get("tokens", "")),
            str(totals.get("cost_usd", "")),
            str(totals.get("duration_ms", "")),
        )
    console.print(table)


@app.command("show")
def observe_show(
    trace_id: str = typer.Argument("latest", help="Trace id or 'latest'"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", "-j"),
    full: bool = typer.Option(False, "--full", help="Dump full JSON (large)"),
) -> None:
    """Show cost/latency/tools/reasoning for a trace."""
    trace = load_trace(trace_id, workspace)
    if trace is None:
        console.print(f"[red]Trace not found:[/red] {trace_id}")
        raise typer.Exit(1)
    if as_json or full:
        typer.echo(trace.model_dump_json(indent=2))
        return
    console.print(render_summary_md(trace))


@app.command("export")
def observe_export(
    trace_id: str = typer.Argument("latest"),
    output: Path = typer.Option(
        Path("aegis-trace-export.json"),
        "--output",
        "-o",
    ),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    markdown: bool = typer.Option(False, "--md", help="Export markdown summary"),
) -> None:
    """Export a trace to JSON or markdown."""
    trace = load_trace(trace_id, workspace)
    if trace is None:
        console.print(f"[red]Trace not found:[/red] {trace_id}")
        raise typer.Exit(1)
    if markdown:
        text = render_summary_md(trace)
        if output.suffix.lower() == ".json":
            output = output.with_suffix(".md")
        output.write_text(text, encoding="utf-8")
    else:
        output.write_text(trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
    console.print(f"Wrote {output}")


@app.command("latest")
def observe_latest(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Shortcut for `observe show latest`."""
    observe_show(trace_id="latest", workspace=workspace, as_json=False, full=False)
