"""Detect and run project tests (unit / integration)."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from aegis.quality.models import CheckResult, CheckStatus, Finding


def _run_cmd(
    command: str,
    cwd: Path,
    *,
    timeout: float = 300.0,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, f"Command timed out after {timeout}s: {command}"
    except OSError as exc:
        return 127, f"Failed to run command: {exc}"


def _tail(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return "…\n" + text[-max_chars:]


def detect_unit_command(workspace: Path) -> str | None:
    """Return a shell command for unit tests, or None if not detected."""
    root = workspace.resolve()
    # Python / pytest
    if (root / "pytest.ini").is_file() or (root / "tests").is_dir():
        if shutil.which("pytest") or _module_available("pytest"):
            return "pytest -q"
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if "pytest" in text and (_module_available("pytest") or shutil.which("pytest")):
            return "pytest -q"
    # Node
    pkg = root / "package.json"
    if pkg.is_file() and shutil.which("npm"):
        try:
            content = pkg.read_text(encoding="utf-8", errors="replace")
            if '"test"' in content:
                return "npm test --silent"
        except OSError:
            pass
    return None


def detect_integration_command(workspace: Path) -> str | None:
    root = workspace.resolve()
    integ_dir = root / "tests" / "integration"
    if integ_dir.is_dir() and any(integ_dir.rglob("test_*.py")):
        if _module_available("pytest") or shutil.which("pytest"):
            return "pytest -q tests/integration"
    # pytest mark — only if project uses it; try dry collection would be heavy
    return None


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def run_unit_tests(workspace: Path, *, timeout: float = 300.0) -> CheckResult:
    started = time.perf_counter()
    cmd = detect_unit_command(workspace)
    if not cmd:
        return CheckResult(
            name="Unit tests",
            status=CheckStatus.SKIP,
            summary="No unit test runner detected",
            required=False,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    code, output = _run_cmd(cmd, workspace, timeout=timeout)
    duration = (time.perf_counter() - started) * 1000
    findings: list[Finding] = []
    if code != 0:
        findings.append(
            Finding(
                severity="critical",
                category="unit_test",
                message="Unit tests failed",
                detail=_tail(output, 1500),
            )
        )
        return CheckResult(
            name="Unit tests",
            status=CheckStatus.FAIL,
            summary=_summarize_pytest(output) or f"exit code {code}",
            required=True,
            findings=findings,
            duration_ms=duration,
            command=cmd,
            output_tail=_tail(output),
        )
    return CheckResult(
        name="Unit tests",
        status=CheckStatus.PASS,
        summary=_summarize_pytest(output) or "passed",
        required=True,
        duration_ms=duration,
        command=cmd,
        output_tail=_tail(output, 2000),
    )


def run_integration_tests(workspace: Path, *, timeout: float = 300.0) -> CheckResult:
    started = time.perf_counter()
    cmd = detect_integration_command(workspace)
    if not cmd:
        return CheckResult(
            name="Integration tests",
            status=CheckStatus.SKIP,
            summary="No integration test suite detected",
            required=False,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    code, output = _run_cmd(cmd, workspace, timeout=timeout)
    duration = (time.perf_counter() - started) * 1000
    if code != 0:
        return CheckResult(
            name="Integration tests",
            status=CheckStatus.FAIL,
            summary=_summarize_pytest(output) or f"exit code {code}",
            required=True,
            findings=[
                Finding(
                    severity="critical",
                    category="integration_test",
                    message="Integration tests failed",
                    detail=_tail(output, 1500),
                )
            ],
            duration_ms=duration,
            command=cmd,
            output_tail=_tail(output),
        )
    return CheckResult(
        name="Integration tests",
        status=CheckStatus.PASS,
        summary=_summarize_pytest(output) or "passed",
        required=True,
        duration_ms=duration,
        command=cmd,
        output_tail=_tail(output, 2000),
    )


def _summarize_pytest(output: str) -> str | None:
    # e.g. "12 passed in 1.23s" or "1 failed, 11 passed"
    m = re.search(
        r"(\d+ failed(?:, \d+ passed)?|\d+ passed(?:, \d+ skipped)?|\d+ error).*",
        output,
    )
    if m:
        return m.group(0).strip()
    m2 = re.search(r"=+ (.*) =+", output)
    if m2:
        return m2.group(1).strip()
    return None
