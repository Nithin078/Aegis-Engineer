"""`aegis doctor` diagnostics command."""

from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis import __version__

console = Console()


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_python_version() -> CheckResult:
    major, minor = sys.version_info[:2]
    version = f"{major}.{minor}.{sys.version_info.micro}"
    ok = (major, minor) >= (3, 12)
    detail = f"Python {version}"
    if not ok:
        detail += " (requires >= 3.12)"
    return CheckResult("Python version", ok, detail)


def _check_package_importable() -> CheckResult:
    spec = importlib.util.find_spec("aegis")
    if spec is None or spec.origin is None:
        return CheckResult("Package import", False, "aegis package not found on PYTHONPATH")
    return CheckResult("Package import", True, str(Path(spec.origin).resolve()))


def _check_cli_entry() -> CheckResult:
    try:
        from aegis.cli.main import app  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult("CLI entry", False, str(exc))
    return CheckResult("CLI entry", True, "aegis.cli.main:app")


def _check_config() -> CheckResult:
    try:
        from aegis.config.loader import get_user_config_path, load_config

        config = load_config()
        path = get_user_config_path()
        location = str(path) if path.is_file() else f"defaults (no file at {path})"
        detail = f"provider={config.provider.default} model={config.provider.model} · {location}"
        return CheckResult("Config", True, detail)
    except Exception as exc:
        return CheckResult("Config", False, str(exc))


def _check_database() -> CheckResult:
    try:
        from aegis.config.loader import get_db_path, load_config
        from aegis.db.connection import init_db
        from aegis.db.migrations import get_schema_version

        config = load_config()
        db_path = get_db_path(config)
        engine = init_db(db_path)
        version = get_schema_version(engine) or "unknown"
        exists = "exists" if db_path.is_file() else "created"
        return CheckResult("Database", True, f"schema v{version} · {exists} · {db_path}")
    except Exception as exc:
        return CheckResult("Database", False, str(exc))


def run_checks() -> list[CheckResult]:
    """Run diagnostic checks. More checks are added in later phases."""
    return [
        CheckResult("Aegis version", True, __version__),
        _check_python_version(),
        CheckResult("Platform", True, platform.platform()),
        _check_package_importable(),
        _check_cli_entry(),
        _check_config(),
        _check_database(),
        # Stub for upcoming phases — not a failure yet.
        CheckResult("LLM provider", True, "not configured yet (Phase 3)"),
    ]


def doctor(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show extra diagnostic detail.",
    ),
) -> None:
    """Run installation and environment diagnostics."""
    results = run_checks()
    table = Table(title="Aegis Doctor", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    failures = 0
    for result in results:
        status = "[green]OK[/green]" if result.ok else "[red]FAIL[/red]"
        if not result.ok:
            failures += 1
        detail = result.detail
        if not verbose and len(detail) > 80:
            detail = detail[:77] + "..."
        table.add_row(result.name, status, detail)

    console.print(table)

    if failures:
        console.print(f"\n[red]{failures} check(s) failed.[/red]")
        raise typer.Exit(code=1)

    console.print("\n[green]All checks passed.[/green]")
