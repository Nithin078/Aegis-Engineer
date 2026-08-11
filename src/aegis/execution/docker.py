"""Docker sandbox with automatic local fallback."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from aegis.execution.models import SandboxResult
from aegis.execution.process import run_command


def docker_available() -> bool:
    """True if the Docker CLI is on PATH and the daemon responds."""
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=8,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode == 0 and bool((proc.stdout or "").strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_in_sandbox(
    cmd: list[str],
    *,
    workspace: Path | str,
    image: str = "python:3.12-slim",
    timeout: float = 120.0,
    mem_limit: str = "512m",
    prefer_docker: bool = True,
    workdir: str = "/workspace",
) -> SandboxResult:
    """
    Run *cmd* inside Docker with the workspace bind-mounted read-write.

    Falls back to a local process when Docker is unavailable or disabled.
    """
    root = Path(workspace).resolve()
    if not prefer_docker or not docker_available():
        local = run_command(cmd, cwd=root, timeout=timeout)
        return SandboxResult(
            backend="local_fallback",
            exit_code=local.exit_code,
            output=local.output,
            image=None,
            error=None if local.ok else (local.stderr or local.stdout)[:2000],
            command=list(cmd),
        )

    # Mount workspace; use host network-free defaults; no --privileged.
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        f"--memory={mem_limit}",
        f"--workdir={workdir}",
        "-v",
        f"{root}:{workdir}",
        image,
        *cmd,
    ]
    try:
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,  # allow image pull overhead
            encoding="utf-8",
            errors="replace",
        )
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return SandboxResult(
            backend="docker",
            exit_code=proc.returncode,
            output=out[-8000:],
            image=image,
            error=None if proc.returncode == 0 else out[-2000:],
            command=list(cmd),
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(
            backend="docker",
            exit_code=124,
            output=f"docker timed out after {timeout}s",
            image=image,
            error="timeout",
            command=list(cmd),
        )
    except OSError as exc:
        # Fall back to local if docker CLI fails unexpectedly
        local = run_command(cmd, cwd=root, timeout=timeout)
        return SandboxResult(
            backend="local_fallback",
            exit_code=local.exit_code,
            output=local.output,
            image=None,
            error=f"docker OSError: {exc}; used local fallback",
            command=list(cmd),
        )


def docker_status() -> dict[str, object]:
    """Diagnostic snapshot for `aegis doctor`."""
    which = shutil.which("docker")
    available = docker_available()
    version = None
    if which:
        try:
            proc = subprocess.run(
                ["docker", "version", "--format", "{{json .Client.Version}}"],
                capture_output=True,
                text=True,
                timeout=8,
                encoding="utf-8",
                errors="replace",
            )
            raw = (proc.stdout or "").strip()
            if raw:
                try:
                    version = json.loads(raw)
                except json.JSONDecodeError:
                    version = raw.strip('"')
        except (OSError, subprocess.TimeoutExpired):
            version = None
    return {
        "cli_path": which,
        "daemon_available": available,
        "client_version": version,
    }
