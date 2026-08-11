"""Phase 11: benchmark harness."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.benchmark.runner import run_benchmarks
from aegis.benchmark.tasks import BUILTIN_TASKS
from aegis.cli.main import app

runner = CliRunner()


def test_builtin_tasks() -> None:
    assert "add_bug" in BUILTIN_TASKS


@pytest.mark.asyncio
async def test_run_add_bug_benchmark(tmp_path: Path) -> None:
    results = await run_benchmarks(["add_bug"], work_root=tmp_path)
    assert len(results) == 1
    assert results[0].success is True
    assert (tmp_path / "last-report.json").is_file()


def test_benchmark_cli_list() -> None:
    r = runner.invoke(app, ["benchmark", "list"])
    assert r.exit_code == 0
    assert "add_bug" in r.stdout
