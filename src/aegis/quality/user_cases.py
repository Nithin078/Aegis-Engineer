"""User-provided extra test cases / commands."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from aegis.quality.models import CheckResult, CheckStatus, Finding


def load_cases_file(path: Path) -> list[str]:
    """Load commands: one non-empty, non-# line per command."""
    lines: list[str] = []
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # strip markdown list prefix
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        lines.append(line)
    return lines


def run_user_cases(
    workspace: Path,
    commands: list[str],
    *,
    timeout: float = 120.0,
) -> CheckResult:
    started = time.perf_counter()
    if not commands:
        return CheckResult(
            name="User cases",
            status=CheckStatus.SKIP,
            summary="No user cases provided",
            required=False,
            duration_ms=0,
        )

    findings: list[Finding] = []
    tails: list[str] = []
    failed = 0
    for i, cmd in enumerate(commands, start=1):
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 124
            out = f"timed out after {timeout}s"
        if code != 0:
            failed += 1
            findings.append(
                Finding(
                    severity="critical",
                    category="user_case",
                    message=f"Case {i} failed (exit {code}): {cmd}",
                    detail=out[-800:] if out else None,
                )
            )
        tails.append(f"$ {cmd}\nexit={code}\n{(out[-500:] if out else '')}")

    duration = (time.perf_counter() - started) * 1000
    if failed:
        return CheckResult(
            name="User cases",
            status=CheckStatus.FAIL,
            summary=f"{failed}/{len(commands)} case(s) failed",
            required=True,
            findings=findings,
            duration_ms=duration,
            output_tail="\n---\n".join(tails)[-4000:],
        )
    return CheckResult(
        name="User cases",
        status=CheckStatus.PASS,
        summary=f"{len(commands)} case(s) passed",
        required=True,
        duration_ms=duration,
        output_tail="\n---\n".join(tails)[-4000:],
    )
