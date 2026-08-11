"""Scan workspace for exposed secrets / API keys (redacted findings)."""

from __future__ import annotations

import re
import time
from pathlib import Path

from aegis.quality.models import CheckResult, CheckStatus, Finding

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".aegis",
    ".tox",
    "htmlcov",
}

_SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".exe",
    ".dll",
    ".so",
    ".pyc",
    ".pyo",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".lock",
}

# name → pattern (must not over-match short words)
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_oauth", re.compile(r"\bgho_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "generic_api_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)"
            r"\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?"
        ),
    ),
]

# Allowlist common placeholders
_PLACEHOLDERS = re.compile(
    r"(?i)(your[_-]?|example|xxx|changeme|placeholder|dummy|fake|test[_-]?key|"
    r"sk-your|gsk_your|env:|<.*>|\{\{.*\}\}|\$\{)"
)


def _redact(match: str) -> str:
    if len(match) <= 8:
        return "***"
    return match[:4] + "…" + match[-4:] + f" (len={len(match)})"


def _is_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDERS.search(text))


def scan_secrets(workspace: Path, *, max_file_bytes: int = 1_000_000) -> CheckResult:
    """Scan text files under workspace for likely secrets."""
    started = time.perf_counter()
    root = workspace.resolve()
    findings: list[Finding] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        # Local env files hold secrets by design; gate targets committed source.
        name = path.name
        if name == ".env" or name.startswith(".env."):
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel = path.relative_to(root).as_posix()
        # Don't fail on scanning our own test fixtures path naming
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            # Skip obvious comments about examples in docs sometimes — still scan
            for kind, pattern in _PATTERNS:
                for m in pattern.finditer(line):
                    raw = m.group(0)
                    # For generic assignment, check captured value
                    if kind == "generic_api_assignment" and m.lastindex and m.lastindex >= 2:
                        raw = m.group(2)
                    if _is_placeholder(raw) or _is_placeholder(line):
                        continue
                    # Avoid matching short false positives
                    if kind == "generic_api_assignment" and len(raw) < 20:
                        continue
                    findings.append(
                        Finding(
                            severity="critical",
                            category="secret",
                            message=f"Possible exposed secret ({kind})",
                            location=f"{rel}:{line_no}",
                            detail=_redact(raw),
                        )
                    )

    duration = (time.perf_counter() - started) * 1000
    if findings:
        return CheckResult(
            name="Secrets scan",
            status=CheckStatus.FAIL,
            summary=f"{len(findings)} potential secret(s) found",
            required=True,
            findings=findings,
            duration_ms=duration,
        )
    return CheckResult(
        name="Secrets scan",
        status=CheckStatus.PASS,
        summary="No obvious secrets found",
        required=True,
        duration_ms=duration,
    )
