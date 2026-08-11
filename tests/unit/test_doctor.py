"""Tests for the doctor command."""

from __future__ import annotations

from typer.testing import CliRunner

from aegis.cli.commands.doctor import run_checks
from aegis.cli.main import app

runner = CliRunner()


def test_run_checks_all_pass_in_dev_env() -> None:
    results = run_checks()
    assert results
    assert all(r.ok for r in results)
    names = {r.name for r in results}
    assert "Python version" in names
    assert "Package import" in names
    assert "CLI entry" in names
    assert "Observability" in names
    assert "Agents" in names
    assert "Tools" in names


def test_doctor_command_success() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout
    assert "Aegis Doctor" in result.stdout


def test_doctor_verbose() -> None:
    result = runner.invoke(app, ["doctor", "--verbose"])
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout
