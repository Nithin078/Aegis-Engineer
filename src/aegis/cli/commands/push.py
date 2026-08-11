"""`aegis push` — git push only if quality gate is SAFE."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from aegis.quality.gate import run_quality_gate
from aegis.quality.models import Verdict
from aegis.quality.report import load_latest_json

console = Console()


def push_command(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    skip_test: bool = typer.Option(
        False,
        "--skip-test",
        help="Skip quality gate (dangerous; prints a warning)",
    ),
    reuse_report: bool = typer.Option(
        False,
        "--reuse-report",
        help="Reuse latest SAFE report if younger than --max-age-minutes",
    ),
    max_age_minutes: int = typer.Option(
        30,
        "--max-age-minutes",
        help="Max age of reused report",
    ),
    lint: bool = typer.Option(False, "--lint", help="Include lint in gate before push"),
    remote: str | None = typer.Option(None, "--remote", "-r", help="Git remote name"),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Branch / refspec"),
) -> None:
    """Run quality gate (unless skipped), then ``git push``."""
    root = workspace.resolve()
    git_dir = root / ".git"
    if not git_dir.exists():
        console.print("[red]Not a git repository.[/red]")
        raise typer.Exit(2)

    if skip_test:
        console.print(
            "[yellow bold]WARNING:[/] Skipping quality gate (--skip-test). "
            "Pushing without Aegis verification."
        )
    else:
        use_cached = False
        if reuse_report:
            latest = load_latest_json(root)
            if latest and latest.get("safe") and latest.get("created_at"):
                try:
                    created = datetime.fromisoformat(latest["created_at"])
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=UTC)
                    age_min = (datetime.now(UTC) - created).total_seconds() / 60.0
                    if age_min <= max_age_minutes:
                        use_cached = True
                        console.print(
                            f"[dim]Reusing SAFE report from {age_min:.1f}m ago "
                            f"({latest.get('report_md_path')})[/dim]"
                        )
                except (TypeError, ValueError):
                    use_cached = False

        if not use_cached:
            console.print("[dim]Running quality gate before push…[/dim]")
            gate = run_quality_gate(root, run_lint_flag=lint)
            if gate.verdict is not Verdict.SAFE:
                console.print(f"[bold red]{gate.verdict.value}[/bold red] — push blocked.")
                if gate.report_md_path:
                    console.print(f"See report: {gate.report_md_path}")
                raise typer.Exit(1)
            console.print(f"[bold green]{gate.verdict.value}[/bold green]")

    args = ["git", "push"]
    if remote:
        args.append(remote)
    if branch:
        args.append(branch)

    console.print(f"[dim]$ {' '.join(args)}[/dim]")
    try:
        proc = subprocess.run(args, cwd=str(root), check=False)
    except OSError as exc:
        console.print(f"[red]git push failed to start: {exc}[/red]")
        raise typer.Exit(1) from exc

    if proc.returncode != 0:
        console.print(f"[red]git push exited {proc.returncode}[/red]")
        raise typer.Exit(proc.returncode)
    console.print("[green]Push complete.[/green]")
