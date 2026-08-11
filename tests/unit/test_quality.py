"""Tests for quality gate (secrets, report, runners, CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.quality.gate import run_quality_gate
from aegis.quality.models import CheckStatus, Verdict
from aegis.quality.report import render_markdown
from aegis.quality.secrets import scan_secrets
from aegis.quality.user_cases import run_user_cases

runner = CliRunner()


@pytest.fixture
def clean_ws(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    return tmp_path


def test_secrets_detects_and_redacts(clean_ws: Path) -> None:
    secret = "sk-" + ("a" * 40)
    (clean_ws / "src" / "leaky.py").write_text(
        f'API_KEY = "{secret}"\n',
        encoding="utf-8",
    )
    result = scan_secrets(clean_ws)
    assert result.status is CheckStatus.FAIL
    assert result.findings
    blob = str(result.findings[0].detail) + result.summary
    assert secret not in blob
    assert "…" in (result.findings[0].detail or "")


def test_secrets_skips_dotenv(clean_ws: Path) -> None:
    secret = "gsk_" + ("b" * 40)
    (clean_ws / ".env").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
    result = scan_secrets(clean_ws)
    assert result.status is CheckStatus.PASS


def test_secrets_ignores_placeholders(clean_ws: Path) -> None:
    (clean_ws / "src" / "config.py").write_text(
        'API_KEY = "sk-your_key_here_xxxxxxxx"\n',
        encoding="utf-8",
    )
    result = scan_secrets(clean_ws)
    assert result.status is CheckStatus.PASS


def test_report_markdown_verdict(clean_ws: Path) -> None:
    report = run_quality_gate(clean_ws, run_unit=False, run_integration=False)
    md = render_markdown(report)
    assert "Aegis Quality Gate Report" in md
    assert report.verdict is Verdict.SAFE
    assert "SAFE TO PUSH" in md
    assert report.report_md_path
    assert Path(report.report_md_path).is_file()


def test_gate_fails_on_secret(clean_ws: Path) -> None:
    (clean_ws / "bad.py").write_text(
        'TOKEN = "ghp_' + ("c" * 40) + '"\n',
        encoding="utf-8",
    )
    report = run_quality_gate(clean_ws, run_unit=False, run_integration=False)
    assert report.verdict is Verdict.NOT_SAFE


def test_user_cases_pass_fail(clean_ws: Path) -> None:
    ok = run_user_cases(clean_ws, ['python -c "print(1)"'])
    assert ok.status is CheckStatus.PASS
    bad = run_user_cases(clean_ws, ['python -c "import sys; sys.exit(2)"'])
    assert bad.status is CheckStatus.FAIL


def test_unit_tests_on_fixture(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    report = run_quality_gate(
        tmp_path,
        run_secrets=False,
        run_integration=False,
    )
    unit = next(c for c in report.checks if c.name == "Unit tests")
    assert unit.status is CheckStatus.PASS
    assert report.verdict is Verdict.SAFE


def test_cli_test_help() -> None:
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0
    assert "quality gate" in result.stdout.lower() or "Quality" in result.stdout


def test_cli_test_on_clean_fixture(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        "def test_x():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["test", "-w", str(tmp_path), "--no-secrets"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "SAFE" in result.stdout


def test_cli_test_blocks_on_secret(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text(
        'k = "sk-' + ("d" * 40) + '"\n',
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["test", "-w", str(tmp_path), "--no-unit", "--no-integration"],
    )
    assert result.exit_code == 1
    assert "NOT SAFE" in result.stdout
