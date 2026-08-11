"""Orchestrate the full quality gate pipeline."""

from __future__ import annotations

from pathlib import Path

from aegis.quality.lint import run_lint
from aegis.quality.models import CheckResult, CheckStatus, Finding, GateReport
from aegis.quality.report import write_reports
from aegis.quality.runners import run_integration_tests, run_unit_tests
from aegis.quality.secrets import scan_secrets
from aegis.quality.user_cases import load_cases_file, run_user_cases


def _docs_check(workspace: Path, *, min_coverage: float = 0.5) -> CheckResult:
    """Optional documentation coverage check for the quality gate."""
    try:
        from aegis.docs_engine.coverage import build_coverage_report
    except ImportError:
        return CheckResult(
            name="Documentation",
            status=CheckStatus.SKIP,
            summary="docs engine not available",
            required=False,
        )
    doc = build_coverage_report(workspace)
    missing = [g for g in doc.gaps if g.kind.value == "missing_file"]
    if missing or doc.coverage < min_coverage:
        findings = [
            Finding(
                severity="warning",
                category="docs",
                message=g.detail,
                location=g.suggested_file,
            )
            for g in doc.gaps[:15]
        ]
        return CheckResult(
            name="Documentation",
            status=CheckStatus.FAIL,
            summary=(
                f"coverage {doc.coverage:.0%}"
                + (f", {len(missing)} missing topic file(s)" if missing else "")
            ),
            required=True,
            findings=findings,
        )
    return CheckResult(
        name="Documentation",
        status=CheckStatus.PASS,
        summary=f"coverage {doc.coverage:.0%}",
        required=True,
    )


def run_quality_gate(
    workspace: Path,
    *,
    run_secrets: bool = True,
    run_lint_flag: bool = False,
    run_unit: bool = True,
    run_integration: bool = True,
    run_docs: bool = False,
    docs_min_coverage: float = 0.5,
    extra_commands: list[str] | None = None,
    cases_file: Path | None = None,
    report_path: Path | None = None,
    test_timeout: float = 300.0,
) -> GateReport:
    """Run all enabled checks and write reports."""
    root = workspace.resolve()
    report = GateReport(workspace=str(root))

    if run_secrets:
        report.checks.append(scan_secrets(root))

    if run_unit:
        report.checks.append(run_unit_tests(root, timeout=test_timeout))

    if run_integration:
        report.checks.append(run_integration_tests(root, timeout=test_timeout))

    if run_lint_flag:
        report.checks.append(run_lint(root))

    if run_docs:
        report.checks.append(_docs_check(root, min_coverage=docs_min_coverage))

    commands: list[str] = list(extra_commands or [])
    if cases_file is not None:
        commands.extend(load_cases_file(cases_file))
    if commands:
        report.checks.append(run_user_cases(root, commands, timeout=test_timeout))

    report.recompute_verdict()
    write_reports(report, root, report_path=report_path)
    return report
