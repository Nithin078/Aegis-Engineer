"""Tests for Phase 8 solve workflow orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.orchestration.models import WorkflowState
from aegis.orchestration.stages import (
    _extract_json,
    _heuristic_classify,
    stage_test,
)
from aegis.orchestration.workflow import run_solve_workflow
from aegis.providers.mock import MockProvider, text_response, tool_then_text

runner = CliRunner()


def _bug_fixture(tmp: Path) -> Path:
    """Repo with buggy add() and a failing test — fix is change - to +."""
    root = tmp / "bugrepo"
    (root / "calc").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "calc" / "__init__.py").write_text("", encoding="utf-8")
    (root / "calc" / "math_ops.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a - b  # bug: should be +\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_math.py").write_text(
        "from calc.math_ops import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    return root


def test_extract_json() -> None:
    assert _extract_json('{"type": "bug"}')["type"] == "bug"
    assert _extract_json('Here:\n{"type": "feature", "x": 1}\n')["type"] == "feature"


def test_heuristic_classify(tmp_path: Path) -> None:
    c = _heuristic_classify("Bug in calc/math_ops.py addition is wrong", tmp_path)
    assert c.type == "bug"
    assert any("math_ops" in f for f in c.estimated_files)


def test_stage_analyze_and_test_on_fixture(tmp_path: Path) -> None:
    root = _bug_fixture(tmp_path)
    from aegis.orchestration.models import WorkflowContext

    ctx = WorkflowContext(issue_text="fix add", workspace=str(root))
    # without ruff maybe skip pass; tests should fail
    tests = stage_test(ctx)
    assert tests.passed is False
    assert tests.command


@pytest.mark.asyncio
async def test_workflow_dry_run_with_mock(tmp_path: Path) -> None:
    root = _bug_fixture(tmp_path)
    classify_json = json.dumps(
        {
            "type": "bug",
            "complexity": "trivial",
            "summary": "add returns wrong result",
            "subsystems": ["calc"],
            "estimated_files": ["calc/math_ops.py"],
        }
    )
    plan_json = json.dumps(
        {
            "summary": "Fix add to use +",
            "risk_level": "low",
            "steps": [
                {
                    "step": 1,
                    "description": "Change subtraction to addition",
                    "files": ["calc/math_ops.py"],
                    "expected_output": "tests pass",
                }
            ],
        }
    )
    retrieve_json = json.dumps(
        {
            "notes": "math_ops add is wrong",
            "snippets": [{"file": "calc/math_ops.py", "lines": "1-3", "reason": "bug"}],
        }
    )
    mock = MockProvider(
        responses=[
            text_response(classify_json),
            text_response(plan_json),
            text_response(retrieve_json),
        ]
    )
    result = await run_solve_workflow(
        issue_text="add(2,3) should be 5 but is wrong in calc/math_ops.py",
        workspace=root,
        provider=mock,
        model="mock",
        dry_run=True,
        max_retries=1,
        use_worktree=False,
        skip_reviews=True,
        memory_enabled=False,
    )
    assert result.context.classification is not None
    assert result.context.classification.type == "bug"
    assert result.context.plan is not None
    assert result.context.plan.steps
    # dry_run skips code; analyze/test pass dry
    assert result.success is True
    assert result.state is WorkflowState.COMPLETE
    assert result.report_path


@pytest.mark.asyncio
async def test_workflow_code_fix_with_mock_edit(tmp_path: Path) -> None:
    root = _bug_fixture(tmp_path)
    classify_json = json.dumps(
        {
            "type": "bug",
            "complexity": "trivial",
            "summary": "fix add",
            "subsystems": ["calc"],
            "estimated_files": ["calc/math_ops.py"],
        }
    )
    plan_json = json.dumps(
        {
            "summary": "Fix operator",
            "risk_level": "low",
            "steps": [{"step": 1, "description": "edit math_ops", "files": ["calc/math_ops.py"]}],
        }
    )
    retrieve_json = json.dumps({"notes": "bug", "snippets": []})

    # Coding agent: call edit tool then summarize
    first, second = tool_then_text(
        "edit",
        json.dumps(
            {
                "path": "calc/math_ops.py",
                "old_string": "return a - b  # bug: should be +",
                "new_string": "return a + b",
            }
        ),
        "Fixed add to use addition.",
    )
    mock = MockProvider(
        responses=[
            text_response(classify_json),
            text_response(plan_json),
            text_response(retrieve_json),
            first,
            second,
        ]
    )
    result = await run_solve_workflow(
        issue_text="Fix add in calc/math_ops.py so add(2,3)==5",
        workspace=root,
        provider=mock,
        model="mock",
        dry_run=False,
        max_retries=2,
        use_worktree=False,
        use_snapshot=True,
        skip_reviews=True,
        memory_enabled=False,
    )
    content = (root / "calc" / "math_ops.py").read_text(encoding="utf-8")
    assert "a + b" in content
    assert result.context.tests is not None
    assert result.context.tests.passed is True
    assert result.success is True


def test_cli_solve_help() -> None:
    r = runner.invoke(app, ["solve", "--help"])
    assert r.exit_code == 0
    assert "solve" in r.stdout.lower()
