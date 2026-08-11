"""Run built-in benchmark tasks."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.benchmark.tasks import BUILTIN_TASKS, BenchmarkTask


@dataclass
class BenchmarkResult:
    task_id: str
    success: bool
    duration_s: float
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def run_task_mock_solve(task: BenchmarkTask, work_root: Path) -> BenchmarkResult:
    """Run the add_bug-style task through the solve workflow with MockProvider."""
    import json as _json

    from aegis.orchestration.workflow import run_solve_workflow
    from aegis.providers.mock import MockProvider, text_response, tool_then_text

    ws = task.materialize(work_root)
    started = time.perf_counter()
    try:
        classify = _json.dumps(
            {
                "type": "bug",
                "complexity": "trivial",
                "summary": task.name,
                "estimated_files": ["calc/math_ops.py"],
            }
        )
        plan = _json.dumps(
            {
                "summary": "Fix operator",
                "risk_level": "low",
                "steps": [
                    {"step": 1, "description": "edit", "files": ["calc/math_ops.py"]}
                ],
            }
        )
        retrieve = _json.dumps({"notes": "bug", "snippets": []})
        # Read current buggy line to craft edit
        src = (ws / "calc" / "math_ops.py").read_text(encoding="utf-8")
        old = "return a - b  # bug" if "return a - b  # bug" in src else "return a - b"
        first, second = tool_then_text(
            "edit",
            _json.dumps(
                {
                    "path": "calc/math_ops.py",
                    "old_string": old,
                    "new_string": "return a + b",
                }
            ),
            "fixed",
        )
        mock = MockProvider(
            responses=[
                text_response(classify),
                text_response(plan),
                text_response(retrieve),
                first,
                second,
            ]
        )
        result = await run_solve_workflow(
            issue_text=task.issue,
            workspace=ws,
            provider=mock,
            model="mock",
            dry_run=False,
            max_retries=2,
            use_worktree=False,
            use_snapshot=True,
            skip_reviews=True,
            memory_enabled=False,
        )
        duration = time.perf_counter() - started
        content = (ws / "calc" / "math_ops.py").read_text(encoding="utf-8")
        ok = result.success and "a + b" in content
        return BenchmarkResult(
            task_id=task.id,
            success=ok,
            duration_s=round(duration, 3),
            error=None if ok else (result.context.error or "fix not applied"),
            details={
                "state": result.state.value,
                "tests_passed": (
                    result.context.tests.passed if result.context.tests else None
                ),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return BenchmarkResult(
            task_id=task.id,
            success=False,
            duration_s=round(time.perf_counter() - started, 3),
            error=str(exc),
        )


async def run_benchmarks(
    task_ids: list[str] | None = None,
    *,
    work_root: Path | None = None,
) -> list[BenchmarkResult]:
    root = work_root or Path.cwd() / ".aegis" / "benchmark"
    root.mkdir(parents=True, exist_ok=True)
    ids = task_ids or list(BUILTIN_TASKS.keys())
    results: list[BenchmarkResult] = []
    for tid in ids:
        task = BUILTIN_TASKS.get(tid)
        if task is None:
            results.append(
                BenchmarkResult(
                    task_id=tid,
                    success=False,
                    duration_s=0.0,
                    error=f"unknown task: {tid}",
                )
            )
            continue
        results.append(await run_task_mock_solve(task, root))
    # write report
    report = {
        "ran_at": datetime.now(UTC).isoformat(),
        "results": [r.to_dict() for r in results],
        "passed": sum(1 for r in results if r.success),
        "total": len(results),
    }
    out = root / "last-report.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return results
