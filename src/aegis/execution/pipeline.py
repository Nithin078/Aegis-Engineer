"""Formatter → linter → tests quality pipeline."""

from __future__ import annotations

from pathlib import Path

from aegis.execution.docker import run_in_sandbox
from aegis.execution.models import PipelineResult, PipelineStepResult
from aegis.execution.process import module_available, python_module_cmd, run_command


def run_quality_pipeline(
    workspace: Path | str,
    *,
    timeout: float = 300.0,
    use_docker: bool = False,
    sandbox_image: str = "python:3.12-slim",
    mem_limit: str = "512m",
    format_code: bool = True,
    lint: bool = True,
    test: bool = True,
) -> PipelineResult:
    """
    Run format (ruff format) → lint (ruff check) → pytest.

    Docker mode runs each step in a container with the workspace mounted.
    When Docker is requested but unavailable, falls back to local automatically.
    """
    root = Path(workspace).resolve()
    result = PipelineResult(passed=True, backend="docker" if use_docker else "local")

    def _run(cmd: list[str], step_timeout: float) -> PipelineStepResult:
        if use_docker:
            sb = run_in_sandbox(
                cmd,
                workspace=root,
                image=sandbox_image,
                timeout=step_timeout,
                mem_limit=mem_limit,
                prefer_docker=True,
            )
            from aegis.execution.models import CommandResult

            cr = CommandResult(
                command=list(cmd),
                command_display=" ".join(cmd),
                exit_code=sb.exit_code,
                stdout=sb.output if sb.exit_code == 0 else "",
                stderr=sb.error or (sb.output if sb.exit_code != 0 else ""),
                backend=sb.backend,
            )
            result.backend = sb.backend
            return PipelineStepResult(name="", result=cr)
        cr = run_command(cmd, cwd=root, timeout=step_timeout)
        result.backend = "local"
        return PipelineStepResult(name="", result=cr)

    # --- format ---
    if format_code:
        if module_available("ruff"):
            step = _run(python_module_cmd("ruff", "format", "."), min(timeout, 120.0))
            step.name = "format"
            result.steps.append(step)
            # format failure is soft — still continue
        else:
            result.steps.append(
                PipelineStepResult(name="format", skipped=True, reason="ruff not installed")
            )
    else:
        result.steps.append(
            PipelineStepResult(name="format", skipped=True, reason="disabled")
        )

    # --- lint ---
    if lint:
        if module_available("ruff"):
            step = _run(python_module_cmd("ruff", "check", "."), min(timeout, 120.0))
            step.name = "lint"
            result.steps.append(step)
            if step.result and not step.result.ok:
                result.passed = False
        else:
            result.steps.append(
                PipelineStepResult(name="lint", skipped=True, reason="ruff not installed")
            )
    else:
        result.steps.append(PipelineStepResult(name="lint", skipped=True, reason="disabled"))

    # --- test ---
    if test:
        has_tests = (root / "tests").is_dir() or (root / "pytest.ini").is_file()
        if not has_tests and (root / "pyproject.toml").is_file():
            text = (root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
            has_tests = "pytest" in text
        if has_tests and module_available("pytest"):
            step = _run(python_module_cmd("pytest", "-q"), timeout)
            step.name = "test"
            result.steps.append(step)
            if step.result and not step.result.ok:
                result.passed = False
        elif has_tests:
            result.steps.append(
                PipelineStepResult(
                    name="test",
                    skipped=True,
                    reason="pytest not installed in this interpreter",
                )
            )
            result.passed = False
        else:
            result.steps.append(
                PipelineStepResult(name="test", skipped=True, reason="no tests detected")
            )
    else:
        result.steps.append(PipelineStepResult(name="test", skipped=True, reason="disabled"))

    return result
