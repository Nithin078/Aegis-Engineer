"""Tests for Repository Intelligence Engine (resolved calls)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.intelligence.engine import IntelligenceEngine, build_intelligence
from aegis.intelligence.graphs import find_cycles
from aegis.intelligence.python_ast import parse_python_file
from aegis.tools.base import ToolContext
from aegis.tools.graph_query import GraphQueryTool
from aegis.tools.registry import create_default_registry

runner = CliRunner()


def _fixture_repo(tmp: Path) -> Path:
    root = tmp / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "util.py").write_text(
        '''
def format_name(name: str) -> str:
    return name.strip().title()

def helper():
    return format_name("x")
''',
        encoding="utf-8",
    )
    (root / "app.py").write_text(
        '''
from util import format_name

def greet(name: str) -> str:
    return f"Hello {format_name(name)}"

def main():
    print(greet("world"))
''',
        encoding="utf-8",
    )
    (root / "pkg" / "service.py").write_text(
        '''
from util import format_name as fn

def process(x: str) -> str:
    return fn(x)

class Worker:
    def run(self, x: str) -> str:
        return process(x)

def factory():
    w = Worker()
    return w.run("hi")
''',
        encoding="utf-8",
    )
    return root


def test_parse_resolves_import_alias(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    symbols, imports, calls, bindings = parse_python_file(root / "app.py", root)
    assert bindings.get("format_name") == "util.format_name"
    assert any(
        c.callee == "util.format_name" and c.confidence.value == "high"
        for c in calls
        if "greet" in c.caller
    )


def test_parse_alias_as(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    _s, _i, calls, bindings = parse_python_file(root / "pkg" / "service.py", root)
    assert bindings.get("fn") == "util.format_name"
    assert any(c.callee == "util.format_name" for c in calls if "process" in c.caller)


def test_self_method_and_constructor(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    _s, _i, calls, _b = parse_python_file(root / "pkg" / "service.py", root)
    # factory: w = Worker(); w.run(...)
    assert any(
        "Worker.run" in c.callee or c.callee.endswith(".run")
        for c in calls
        if "factory" in c.caller
    )
    # self in run -> process
    assert any(
        "process" in c.callee for c in calls if c.caller.endswith("Worker.run")
    )


def test_build_and_who_calls_resolved(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    index = build_intelligence(root)
    assert index.stats.resolved_calls >= 1
    eng = IntelligenceEngine(root)
    # high-confidence callers of util.format_name
    callers = eng.callers("util.format_name")
    caller_names = {c["caller"] for c in callers}
    assert any("greet" in c for c in caller_names)
    assert any("process" in c or "helper" in c for c in caller_names)

    q = eng.query("who calls format_name")
    assert q["type"] == "callers"
    assert q["count"] >= 1
    assert q.get("definitions")


def test_impact_and_search(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    eng = IntelligenceEngine(root)
    eng.build()
    impact = eng.impact("util.py")
    assert impact["risk_level"] in {"low", "medium", "high"}
    assert len(impact.get("callers") or []) >= 1

    hits = eng.search("format name")
    assert any("format_name" in (h.get("qualname") or "") for h in hits)


def test_import_cycles(tmp_path: Path) -> None:
    root = tmp_path / "cyc"
    root.mkdir()
    (root / "a.py").write_text("import b\n", encoding="utf-8")
    (root / "b.py").write_text("import a\n", encoding="utf-8")
    eng = IntelligenceEngine(root)
    eng.build()
    assert eng._import_g is not None
    assert find_cycles(eng._import_g)


def test_graph_query_tool(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    build_intelligence(root)
    reg = create_default_registry()
    assert reg.get("graph_query") is not None
    tool = GraphQueryTool()
    ctx = ToolContext(workspace_root=root, agent="test")
    import asyncio

    result = asyncio.run(tool.run({"op": "callers", "target": "format_name"}, ctx))
    assert not result.error
    assert "caller" in result.output or "results" in result.output


def test_cli_intelligence(tmp_path: Path) -> None:
    root = _fixture_repo(tmp_path)
    r = runner.invoke(app, ["intelligence", "build", "-w", str(root)])
    assert r.exit_code == 0, r.stdout + r.stderr

    r = runner.invoke(
        app,
        ["intelligence", "callers", "format_name", "-w", str(root), "--json"],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "callers" in r.stdout or "greet" in r.stdout

    r = runner.invoke(
        app,
        ["intelligence", "query", "who calls format_name", "-w", str(root), "--json"],
    )
    assert r.exit_code == 0
    assert "callers" in r.stdout
