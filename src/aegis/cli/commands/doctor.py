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


def _check_llm_provider() -> CheckResult:
    try:
        from aegis.providers.factory import provider_configured

        _has_key, detail = provider_configured()
        # Missing keys are informational for doctor (run will fail hard if needed).
        return CheckResult("LLM provider", True, detail)
    except Exception as exc:
        return CheckResult("LLM provider", False, str(exc))


def _check_git() -> CheckResult:
    import shutil
    import subprocess

    if not shutil.which("git"):
        return CheckResult("Git", False, "git not found on PATH")
    try:
        proc = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        detail = (proc.stdout or proc.stderr or "").strip() or "git available"
        return CheckResult("Git", proc.returncode == 0, detail)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult("Git", False, str(exc))


def _check_docker() -> CheckResult:
    try:
        from aegis.execution.docker import docker_status

        st = docker_status()
        if st.get("daemon_available"):
            ver = st.get("client_version") or "unknown"
            return CheckResult("Docker", True, f"daemon up · client {ver}")
        if st.get("cli_path"):
            return CheckResult(
                "Docker",
                True,
                f"CLI at {st['cli_path']} (daemon unavailable — local fallback)",
            )
        return CheckResult("Docker", True, "not installed (local execution fallback)")
    except Exception as exc:
        return CheckResult("Docker", False, str(exc))


def _check_github_token() -> CheckResult:
    try:
        from aegis.github.client import resolve_github_token

        token = resolve_github_token()
        if token:
            return CheckResult("GitHub token", True, "GITHUB_TOKEN/GH_TOKEN set")
        return CheckResult(
            "GitHub token",
            True,
            "not set (optional — needed for private issues / PR create)",
        )
    except Exception as exc:
        return CheckResult("GitHub token", False, str(exc))


def _check_tools() -> CheckResult:
    try:
        from aegis.tools.registry import create_default_registry

        reg = create_default_registry()
        names = sorted(t.name for t in reg.list_tools())
        return CheckResult("Tools", True, f"{len(names)} registered: {', '.join(names[:8])}…")
    except Exception as exc:
        return CheckResult("Tools", False, str(exc))


def _check_agents() -> CheckResult:
    try:
        from aegis.agents.specialists import AGENT_FACTORIES

        names = ", ".join(sorted(AGENT_FACTORIES))
        return CheckResult("Agents", True, f"{len(AGENT_FACTORIES)} specialists: {names}")
    except Exception as exc:
        return CheckResult("Agents", False, str(exc))


def _check_intelligence() -> CheckResult:
    try:
        from aegis.intelligence.engine import IntelligenceEngine

        _ = IntelligenceEngine
        return CheckResult(
            "Intelligence",
            True,
            "Python AST/NetworkX ready; JS/TS deferred (see LANGUAGE_MATRIX)",
        )
    except Exception as exc:
        return CheckResult("Intelligence", False, str(exc))


def _check_observability() -> CheckResult:
    try:
        from aegis.observability.models import SessionTrace

        _ = SessionTrace()
        return CheckResult("Observability", True, "trace collector + observe CLI")
    except Exception as exc:
        return CheckResult("Observability", False, str(exc))


def _check_plugins() -> CheckResult:
    try:
        from aegis.plugins.hooks import get_hooks

        counts = get_hooks().list_hooks()
        return CheckResult(
            "Plugins",
            True,
            f"hooks ready ({sum(counts.values())} registered): {counts}",
        )
    except Exception as exc:
        return CheckResult("Plugins", False, str(exc))


def run_checks() -> list[CheckResult]:
    """Run installation and environment diagnostics."""
    return [
        CheckResult("Aegis version", True, __version__),
        _check_python_version(),
        CheckResult("Platform", True, platform.platform()),
        _check_package_importable(),
        _check_cli_entry(),
        _check_config(),
        _check_database(),
        _check_llm_provider(),
        _check_git(),
        _check_docker(),
        _check_github_token(),
        _check_tools(),
        _check_agents(),
        _check_intelligence(),
        _check_observability(),
        _check_plugins(),
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
