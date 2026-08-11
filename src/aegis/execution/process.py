"""Local process execution with timeouts and env control."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from aegis.execution.models import CommandResult


def run_command(
    cmd: list[str],
    *,
    cwd: Path | str,
    timeout: float = 120.0,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a command list (no shell) and capture output."""
    root = Path(cwd).resolve()
    full_env = dict(env if env is not None else os.environ)
    if extra_env:
        full_env.update(extra_env)
    # Prefer workspace on PYTHONPATH for package imports in fixtures.
    existing = full_env.get("PYTHONPATH", "")
    path_parts = [str(root)]
    if existing:
        path_parts.append(existing)
    full_env["PYTHONPATH"] = os.pathsep.join(path_parts)

    display = " ".join(cmd)
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=full_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.perf_counter() - started
        return CommandResult(
            command=list(cmd),
            command_display=display,
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_s=duration,
            timed_out=False,
            backend="local",
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else str(exc)
        return CommandResult(
            command=list(cmd),
            command_display=display,
            exit_code=124,
            stdout=out,
            stderr=err or f"timed out after {timeout}s",
            duration_s=duration,
            timed_out=True,
            backend="local",
        )
    except OSError as exc:
        duration = time.perf_counter() - started
        return CommandResult(
            command=list(cmd),
            command_display=display,
            exit_code=127,
            stdout="",
            stderr=str(exc),
            duration_s=duration,
            timed_out=False,
            backend="local",
        )


def python_module_cmd(*module_and_args: str) -> list[str]:
    """Build `[sys.executable, -m, ...]` for the current interpreter."""
    return [sys.executable, "-m", *module_and_args]


def module_available(module: str) -> bool:
    """Return True if `python -m <module> --version` (or -h) succeeds."""
    for flag in ("--version", "-h"):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", module, flag],
                capture_output=True,
                timeout=20,
            )
            if proc.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False
