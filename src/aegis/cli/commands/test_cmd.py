"""`aegis test` — quality gate with markdown report."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.quality.gate import run_quality_gate
from aegis.quality.models import CheckStatus, Verdict
from aegis.quality.report import status_emoji

console = Console()

app = typer.Typer(
    name="test",
    help="Run the quality gate (secrets, tests, optional lint) and write a markdown report.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def test_command(
    ctx: typer.Context,
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        help="Project root to test",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    lint: bool = typer.Option(False, "--lint", help="Also run linter (ruff/eslint if found)"),
    no_secrets: bool = typer.Option(False, "--no-secrets", help="Skip secrets scan"),
    no_unit: bool = typer.Option(False, "--no-unit", help="Skip unit tests"),
    no_integration: bool = typer.Option(
        False, "--no-integration", help="Skip integration tests"
    ),
    extra: list[str] | None = typer.Option(
        None,
        "--extra",
        "-e",
        help="Extra shell command to run as a user case (repeatable)",
    ),
    cases: Path | None = typer.Option(
        None,
        "--cases",
        help="File with one extra command per line",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    report: Path | None = typer.Option(
        None,
        "--report",
        "-o",
        help="Custom markdown report path",
        dir_okay=False,
    ),
    as_json: bool = typer.Option(False, "--json", "-j", help="Print JSON summary to stdout"),
    timeout: float = typer.Option(300.0, "--timeout", help="Per-command timeout seconds"),
    docs: bool = typer.Option(
        False,
        "--docs",
        help="Include documentation coverage check (living docs)",
    ),
    docs_min_coverage: float = typer.Option(
        0.5,
        "--docs-min-coverage",
        help="Min doc coverage when --docs is set (0-1)",
    ),
) -> None:
    """Run secrets scan, tests, optional lint; write CodeRabbit-style MD report."""
    if ctx.invoked_subcommand is not None:
        return

    gate = run_quality_gate(
        workspace,
        run_secrets=not no_secrets,
        run_lint_flag=lint,
        run_unit=not no_unit,
        run_integration=not no_integration,
        run_docs=docs,
        docs_min_coverage=docs_min_coverage,
        extra_commands=list(extra or []),
        cases_file=cases,
        report_path=report,
        test_timeout=timeout,
    )

    if as_json:
        typer.echo(json.dumps(gate.to_summary_dict(), indent=2))
    else:
        table = Table(title="Aegis Quality Gate", show_header=True, header_style="bold")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        for c in gate.checks:
            emoji = status_emoji(c.status)
            style = (
                "green"
                if c.status is CheckStatus.PASS
                else (
                    "yellow"
                    if c.status is CheckStatus.SKIP
                    else "red"
                )
            )
            table.add_row(c.name, f"[{style}]{emoji} {c.status.value}[/{style}]", c.summary)
        console.print(table)
        console.print()
        if gate.verdict is Verdict.SAFE:
            console.print(f"[bold green]{gate.verdict.value}[/bold green]")
        else:
            console.print(f"[bold red]{gate.verdict.value}[/bold red]")
        if gate.report_md_path:
            console.print(f"[dim]Report: {gate.report_md_path}[/dim]")

    if gate.verdict is Verdict.SAFE:
        raise typer.Exit(0)
    raise typer.Exit(1)


@app.command("install-hook")
def install_hook(
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
    """Install a git pre-push hook that runs `aegis test`."""
    git_dir = workspace / ".git"
    if not git_dir.is_dir():
        console.print("[red]Not a git repository (no .git directory).[/red]")
        raise typer.Exit(2)

    hooks = git_dir / "hooks"
    hooks.mkdir(exist_ok=True)
    hook_path = hooks / "pre-push"
    script = """#!/bin/sh
# Aegis quality gate — installed by `aegis test install-hook`
if command -v aegis >/dev/null 2>&1; then
  aegis test -w "$(git rev-parse --show-toplevel)" || {
    echo "aegis test failed - push blocked. Fix or: aegis push --skip-test"
    exit 1
  }
else
  echo "warning: aegis not on PATH; pre-push hook skipped"
fi
exit 0
"""
    hook_path.write_text(script, encoding="utf-8", newline="\n")
    try:
        hook_path.chmod(hook_path.stat().st_mode | 0o111)
    except OSError:
        pass
    console.print(f"[green]Installed[/green] pre-push hook → {hook_path}")
    console.print("[dim]Raw `git push` will now run `aegis test` when `aegis` is on PATH.[/dim]")
