"""Phase 10: reviews + memory-informed planning in solve workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis.memory.store import MemoryStore
from aegis.orchestration.models import WorkflowState
from aegis.orchestration.workflow import run_solve_workflow
from aegis.providers.mock import MockProvider, text_response, tool_then_text


def _bug_fixture(tmp: Path) -> Path:
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
    (root / "README.md").write_text("# Calc\nSimple math helpers.\n", encoding="utf-8")
    return root


def _scripted_responses(*, with_code: bool = False) -> list:
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
            "steps": [
                {
                    "step": 1,
                    "description": "edit math_ops",
                    "files": ["calc/math_ops.py"],
                }
            ],
        }
    )
    retrieve_json = json.dumps({"notes": "bug in add", "snippets": []})
    responses = [
        text_response(classify_json),
        text_response(plan_json),
        text_response(retrieve_json),
    ]
    if with_code:
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
        responses.extend([first, second])
    return responses


@pytest.mark.asyncio
async def test_workflow_writes_memory_and_reviews(tmp_path: Path) -> None:
    root = _bug_fixture(tmp_path)
    mock = MockProvider(responses=_scripted_responses(with_code=True))
    result = await run_solve_workflow(
        issue_text="Fix add in calc/math_ops.py so add(2,3)==5",
        workspace=root,
        provider=mock,
        model="mock",
        dry_run=False,
        max_retries=2,
        use_worktree=False,
        use_snapshot=True,
        skip_reviews=False,
        memory_enabled=True,
    )
    assert result.success is True
    assert result.state is WorkflowState.COMPLETE
    assert result.context.reviews is not None
    assert result.context.reviews.security is not None
    assert result.context.pr_draft is not None
    assert result.context.pr_draft.pr_title
    # memory recorded under original workspace
    store = MemoryStore(root)
    solved = store.list_entries(kind="solved")
    assert len(solved) >= 1
    assert "a + b" in (root / "calc" / "math_ops.py").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_second_issue_sees_memory_hints(tmp_path: Path) -> None:
    root = _bug_fixture(tmp_path)
    store = MemoryStore(root)
    store.record_solved(
        issue_text="Fix add in calc/math_ops.py so add(2,3)==5",
        summary="Changed subtraction to addition in math_ops",
        classification="bug",
        files=["calc/math_ops.py"],
        plan_summary="Use + not -",
        tags=["bug", "math"],
    )
    mock = MockProvider(responses=_scripted_responses(with_code=False))
    result = await run_solve_workflow(
        issue_text="add(2,3) still wrong? check calc/math_ops.py addition",
        workspace=root,
        provider=mock,
        model="mock",
        dry_run=True,
        max_retries=1,
        use_worktree=False,
        memory_enabled=True,
    )
    assert result.success is True
    assert result.context.plan is not None
    # memory_hits populated during plan
    assert result.context.memory_hits
    assert result.context.plan.memory_hints
    # docs collected from README
    assert result.context.context is not None
    assert any(d.get("path") == "README.md" for d in result.context.context.docs)


@pytest.mark.asyncio
async def test_skip_reviews_flag(tmp_path: Path) -> None:
    root = _bug_fixture(tmp_path)
    mock = MockProvider(responses=_scripted_responses(with_code=False))
    result = await run_solve_workflow(
        issue_text="plan only",
        workspace=root,
        provider=mock,
        model="mock",
        dry_run=True,
        skip_reviews=True,
        memory_enabled=False,
        use_worktree=False,
    )
    assert result.success is True
    assert result.context.reviews is None
    assert result.context.pr_draft is not None  # still drafts PR in dry-run
