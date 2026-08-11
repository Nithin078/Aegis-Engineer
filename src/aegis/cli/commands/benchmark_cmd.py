"""`aegis benchmark` — lightweight evaluation harness."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.benchmark.tasks import BUILTIN_TASKS

console = Console()

app = typer.Typer(
    name="benchmark",
    help="Run built-in evaluation tasks (SWE-bench later).",
    no_args_is_help=True,
)


@app.command("list")
def benchmark_list(
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """List available benchmark tasks."""
    rows = [
        {"id": t.id, "name": t.name, "description": t.description}
        for t in BUILTIN_TASKS.values()
    ]
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    table = Table(title="Benchmark tasks")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Description")
    for r in rows:
        table.add_row(r["id"], r["name"], r["description"])
    console.print(table)


@app.command("run")
def benchmark_run(
    task: str | None = typer.Option(
        None,
        "--task",
        "-t",
        help="Task id (default: all built-in)",
    ),
    work_dir: Path = typer.Option(
        Path(".aegis/benchmark"),
        "--work-dir",
        help="Where fixture workspaces are written",
    ),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Run benchmark task(s) with the mock solve path (no API key required)."""
    from aegis.benchmark.runner import run_benchmarks

    ids = [task] if task else None
    if task and task not in BUILTIN_TASKS:
        console.print(f"[red]Unknown task:[/red] {task}")
        console.print(f"Available: {', '.join(BUILTIN_TASKS)}")
        raise typer.Exit(1)

    results = asyncio.run(run_benchmarks(ids, work_root=work_dir))
    if as_json:
        typer.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        table = Table(title="Benchmark results")
        table.add_column("Task")
        table.add_column("OK")
        table.add_column("Seconds")
        table.add_column("Error")
        for r in results:
            table.add_row(
                r.task_id,
                "[green]pass[/green]" if r.success else "[red]fail[/red]",
                f"{r.duration_s:.2f}",
                r.error or "",
            )
        console.print(table)
        passed = sum(1 for r in results if r.success)
        console.print(f"{passed}/{len(results)} passed")
        console.print(f"[dim]Report: {work_dir / 'last-report.json'}[/dim]")

    if not all(r.success for r in results):
        raise typer.Exit(1)
