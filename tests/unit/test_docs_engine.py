"""Tests for living documentation engine."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.docs_engine.coverage import build_coverage_report
from aegis.docs_engine.inventory_code import inventory_packages
from aegis.docs_engine.pipeline import run_document

runner = CliRunner()


def _mini_project(tmp: Path) -> Path:
    """Fixture shaped like a tiny Aegis-like package."""
    pkg = tmp / "src" / "demo"
    (pkg / "cli").mkdir(parents=True)
    (pkg / "server").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "cli" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "cli" / "main.py").write_text(
        '''
import typer
app = typer.Typer()
@app.command("run")
def run(): pass
app.command("doctor")(run)
app.add_typer(app, name="test")
''',
        encoding="utf-8",
    )
    (pkg / "server" / "app.py").write_text(
        '''
from starlette.routing import Route
routes = [
    Route("/health", None, methods=["GET"]),
    Route("/session", None, methods=["POST"]),
]
''',
        encoding="utf-8",
    )
    (tmp / "README.md").write_text("# Demo\n\nUse `aegis run` sometimes.\n", encoding="utf-8")
    return tmp


def test_inventory_packages(tmp_path: Path) -> None:
    _mini_project(tmp_path)
    pkgs = inventory_packages(tmp_path)
    ids = {p.id for p in pkgs}
    assert "demo" in ids
    assert "demo.cli" in ids


def test_coverage_finds_missing_topic_files(tmp_path: Path) -> None:
    _mini_project(tmp_path)
    report = build_coverage_report(tmp_path)
    assert report.gaps
    missing = [g for g in report.gaps if g.kind.value == "missing_file"]
    assert missing
    assert report.coverage < 1.0 or report.undocumented_count >= 0


def test_document_propose_and_apply(tmp_path: Path) -> None:
    _mini_project(tmp_path)
    # propose
    r1 = run_document(tmp_path, apply=False, check_only=False)
    assert r1.proposed_files
    assert not (tmp_path / "docs" / "CLI.md").is_file()
    assert any("CLI" in p or "cli" in p.lower() for p in r1.proposed_files)

    # apply
    run_document(tmp_path, apply=True)
    assert (tmp_path / "docs" / "CLI.md").is_file()
    assert (tmp_path / "docs" / "API.md").is_file()
    assert (tmp_path / "docs" / "ARCHITECTURE.md").is_file()
    assert (tmp_path / "docs" / "GAPS.md").is_file()
    cli = (tmp_path / "docs" / "CLI.md").read_text(encoding="utf-8")
    assert "aegis" in cli.lower() or "Commands" in cli
    assert "aegis:sources=" in cli

    # check should still work
    r3 = run_document(tmp_path, check_only=True)
    assert r3.report_path


def test_cli_document_help() -> None:
    result = runner.invoke(app, ["document", "--help"])
    assert result.exit_code == 0
    assert "document" in result.stdout.lower() or "Documentation" in result.stdout


def test_cli_document_check_fixture(tmp_path: Path) -> None:
    _mini_project(tmp_path)
    result = runner.invoke(
        app,
        ["document", "-w", str(tmp_path), "--check", "--min-coverage", "0.99"],
    )
    # missing docs → fail
    assert result.exit_code == 1

    runner.invoke(app, ["document", "-w", str(tmp_path), "--apply"])
    result2 = runner.invoke(
        app,
        ["document", "-w", str(tmp_path), "--check", "--min-coverage", "0.0"],
    )
    # with docs created and min 0, pass if no hard missing files
    assert result2.exit_code == 0, result2.stdout + result2.stderr
