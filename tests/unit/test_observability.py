"""Phase 11: observability traces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.cli.main import app
from aegis.observability.collector import collect_trace
from aegis.observability.store import list_traces, load_trace, render_summary_md, save_trace

runner = CliRunner()


@pytest.mark.asyncio
async def test_collector_from_bus(tmp_path: Path) -> None:
    bus = EventBus()
    with collect_trace(bus, workspace=tmp_path, workflow="test") as col:
        col.mark_phase("plan", enter=True)
        await bus.publish(EventType.AGENT_START, {"agent": "planner", "task": "plan it"})
        await bus.publish(
            EventType.AGENT_DONE,
            {"agent": "planner", "tokens": 100, "cost_usd": 0.001, "iterations": 1},
        )
        col.mark_phase("plan", enter=False)
        col.reason("decided to edit math_ops", agent="planner")
        trace = col.finish(success=True)
    assert trace.success is True
    assert any(e.agent == "planner" for e in trace.events)
    assert trace.costs
    assert trace.latency
    assert trace.reasoning
    path = save_trace(trace, tmp_path)
    assert path.is_file()
    loaded = load_trace(trace.id, tmp_path)
    assert loaded is not None
    assert loaded.id == trace.id
    md = render_summary_md(loaded)
    assert "Cost breakdown" in md
    rows = list_traces(tmp_path)
    assert rows


@pytest.mark.asyncio
async def test_solve_writes_trace(tmp_path: Path) -> None:
    from aegis.orchestration.workflow import run_solve_workflow
    from aegis.providers.mock import MockProvider, text_response

    root = tmp_path / "ws"
    root.mkdir()
    (root / "README.md").write_text("# x\n", encoding="utf-8")
    mock = MockProvider(
        responses=[
            text_response(
                json.dumps(
                    {
                        "type": "docs",
                        "complexity": "trivial",
                        "summary": "noop",
                        "estimated_files": [],
                    }
                )
            ),
            text_response(
                json.dumps(
                    {
                        "summary": "noop",
                        "risk_level": "low",
                        "steps": [{"step": 1, "description": "none", "files": []}],
                    }
                )
            ),
            text_response(json.dumps({"notes": "n", "snippets": []})),
        ]
    )
    result = await run_solve_workflow(
        issue_text="document only dry",
        workspace=root,
        provider=mock,
        model="mock",
        dry_run=True,
        use_worktree=False,
        skip_reviews=True,
        memory_enabled=False,
    )
    assert result.success
    assert result.context.meta.get("trace_id")
    trace = load_trace("latest", root)
    assert trace is not None
    assert trace.workflow == "solve"
    assert (root / ".aegis" / "traces" / "latest.json").is_file()


def test_observe_cli_help() -> None:
    r = runner.invoke(app, ["observe", "--help"])
    assert r.exit_code == 0
    assert "list" in r.stdout
