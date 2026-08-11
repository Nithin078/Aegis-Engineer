"""Optional linters for the quality gate."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from aegis.quality.models import CheckResult, CheckStatus, Finding


def run_lint(workspace: Path, *, timeout: float = 120.0) -> CheckResult:
    started = time.perf_counter()
    root = workspace.resolve()
    cmd: str | None = None

    if shutil.which("ruff") and (
        (root / "pyproject.toml").is_file()
        or (root / "ruff.toml").is_file()
        or any(root.glob("**/*.py"))
    ):
        cmd = "ruff check ."
    elif (root / "package.json").is_file() and shutil.which("npx"):
        cmd = "npx --yes eslint . --max-warnings 0"

    if not cmd:
        return CheckResult(
            name="Lint",
            status=CheckStatus.SKIP,
            summary="No linter detected",
            required=False,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        code = proc.returncode
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="Lint",
            status=CheckStatus.ERROR,
            summary=f"Lint timed out after {timeout}s",
            required=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            command=cmd,
        )

    duration = (time.perf_counter() - started) * 1000
    if code != 0:
        return CheckResult(
            name="Lint",
            status=CheckStatus.FAIL,
            summary="Linter reported issues",
            required=True,
            findings=[
                Finding(
                    severity="warning",
                    category="lint",
                    message="Lint failed",
                    detail=out[-1500:] if out else f"exit {code}",
                )
            ],
            duration_ms=duration,
            command=cmd,
            output_tail=out[-4000:] if out else None,
        )
    return CheckResult(
        name="Lint",
        status=CheckStatus.PASS,
        summary="Lint clean",
        required=True,
        duration_ms=duration,
        command=cmd,
        output_tail=out[-2000:] if out else None,
    )
