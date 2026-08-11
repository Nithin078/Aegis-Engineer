"""`aegis document` — living documentation with coverage & drift control."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.docs_engine.pipeline import run_document

console = Console()


def document_command(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write docs into the repo (docs/CLI.md, …). Default: docs/_proposed/",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="CI mode: analyze only, exit 1 if coverage/gaps fail thresholds",
    ),
    min_coverage: float = typer.Option(
        0.0,
        "--min-coverage",
        help="Minimum documentation coverage (0-1) for --check success",
    ),
    fail_on_stale: bool = typer.Option(
        False,
        "--fail-on-stale",
        help="With --check, fail if stale doc references exist",
    ),
    report: Path | None = typer.Option(
        None,
        "--report",
        "-o",
        help="Custom path for the docs report markdown",
    ),
    as_json: bool = typer.Option(False, "--json", "-j", help="Print JSON summary"),
) -> None:
    """Compare code surface to docs; create/update topic markdown files."""
    if check and apply:
        console.print("[red]Use either --check or --apply, not both.[/red]")
        raise typer.Exit(2)

    result = run_document(
        workspace,
        apply=apply and not check,
        check_only=check,
        min_coverage=min_coverage,
        allow_stale=not fail_on_stale,
        report_path=report,
    )

    if as_json:
        typer.echo(json.dumps(result.to_summary_dict(), indent=2))
    else:
        table = Table(title="Aegis Document", show_header=True, header_style="bold")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Coverage", f"{result.coverage:.1%}")
        table.add_row("Surfaces", str(len(result.surfaces)))
        table.add_row("Documented", str(len(result.documented_ids)))
        table.add_row("Undocumented", str(result.undocumented_count))
        table.add_row("Stale", str(result.stale_count))
        table.add_row("Gaps", str(len(result.gaps)))
        table.add_row("Actions", str(len(result.actions)))
        console.print(table)

        if result.written_files:
            console.print("[green]Written:[/green] " + ", ".join(result.written_files))
        if result.proposed_files:
            console.print(
                "[cyan]Proposed:[/cyan] "
                + ", ".join(result.proposed_files[:8])
                + (" …" if len(result.proposed_files) > 8 else "")
            )
            console.print("[dim]Re-run with --apply to write into docs/[/dim]")
        if result.report_path:
            console.print(f"[dim]Report: {result.report_path}[/dim]")

    if check:
        ok = result.passes_check(
            min_coverage=min_coverage,
            allow_stale=not fail_on_stale,
        )
        # Also fail if required topic files missing
        missing = [g for g in result.gaps if g.kind.value == "missing_file"]
        if missing:
            ok = False
        if not ok:
            console.print("[bold red]Documentation check FAILED[/bold red]")
            raise typer.Exit(1)
        console.print("[bold green]Documentation check PASSED[/bold green]")
        raise typer.Exit(0)
