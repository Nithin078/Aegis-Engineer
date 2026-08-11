"""Phase 9: execution process, docker fallback, quality pipeline."""

from __future__ import annotations

from pathlib import Path

from aegis.execution.docker import docker_available, docker_status, run_in_sandbox
from aegis.execution.pipeline import run_quality_pipeline
from aegis.execution.process import module_available, python_module_cmd, run_command


def _mini_repo(tmp: Path) -> Path:
    root = tmp / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "math_ops.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_math.py").write_text(
        "from pkg.math_ops import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    return root


def test_run_command_echo(tmp_path: Path) -> None:
    import sys

    r = run_command([sys.executable, "-c", "print('hi')"], cwd=tmp_path, timeout=15)
    assert r.ok
    assert "hi" in r.stdout
    assert r.backend == "local"


def test_python_module_cmd() -> None:
    cmd = python_module_cmd("pytest", "-q")
    assert cmd[-2:] == ["pytest", "-q"]
    assert "-m" in cmd


def test_pipeline_local_passes(tmp_path: Path) -> None:
    root = _mini_repo(tmp_path)
    result = run_quality_pipeline(
        root,
        use_docker=False,
        format_code=False,
        lint=module_available("ruff"),
        test=True,
    )
    test_step = result.step("test")
    assert test_step is not None
    assert not test_step.skipped
    assert test_step.result is not None
    assert test_step.result.ok
    assert result.passed


def test_pipeline_detects_failure(tmp_path: Path) -> None:
    root = _mini_repo(tmp_path)
    (root / "pkg" / "math_ops.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a - b\n",
        encoding="utf-8",
    )
    result = run_quality_pipeline(
        root, use_docker=False, format_code=False, lint=False, test=True
    )
    assert result.passed is False
    test_step = result.step("test")
    assert test_step and test_step.result and not test_step.result.ok


def test_sandbox_local_fallback(tmp_path: Path) -> None:
    import sys

    root = _mini_repo(tmp_path)
    sb = run_in_sandbox(
        [sys.executable, "-m", "pytest", "-q"],
        workspace=root,
        prefer_docker=False,
        timeout=60,
    )
    assert sb.backend == "local_fallback"
    assert sb.ok


def test_docker_status_shape() -> None:
    st = docker_status()
    assert "cli_path" in st
    assert "daemon_available" in st
    # docker_available should match status flag
    assert docker_available() is bool(st["daemon_available"])
