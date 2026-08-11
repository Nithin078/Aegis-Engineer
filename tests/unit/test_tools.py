"""Tests for core tools and registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.config.schema import PermissionRule, PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """Small sample repo for tool tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "hello.py").write_text(
        "def greet(name: str) -> str:\n    return f'hello {name}'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "math_util.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Fixture\n\nSample repo.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def ctx(fixture_repo: Path) -> ToolContext:
    return ToolContext(workspace_root=fixture_repo, agent="coder", timeout=10.0)


@pytest.mark.asyncio
async def test_read_write_edit_glob_grep(fixture_repo: Path, ctx: ToolContext) -> None:
    bus = EventBus()
    bus.enable_history(True)
    eng = PermissionEngine(
        PermissionsConfig(
            default="allow",
            trust_mode="yolo",
            rules=[PermissionRule(tool="*", agent="*", level="allow")],
        )
    )
    registry = create_default_registry(permission_engine=eng, event_bus=bus)
    ctx.event_bus = bus

    # read
    result = await registry.execute("read", {"path": "src/hello.py"}, ctx)
    assert not result.error
    assert "greet" in result.output
    assert "1|" in result.output or "     1|" in result.output

    # write
    result = await registry.execute(
        "write",
        {"path": "src/new.py", "content": "x = 1\n"},
        ctx,
    )
    assert not result.error
    assert (fixture_repo / "src" / "new.py").read_text(encoding="utf-8") == "x = 1\n"

    # edit
    result = await registry.execute(
        "edit",
        {"path": "src/new.py", "old_string": "x = 1", "new_string": "x = 2"},
        ctx,
    )
    assert not result.error
    assert "x = 2" in (fixture_repo / "src" / "new.py").read_text(encoding="utf-8")

    # glob
    result = await registry.execute("glob", {"pattern": "**/*.py"}, ctx)
    assert not result.error
    assert "src/hello.py" in result.output.replace("\\", "/")
    assert result.metadata["count"] >= 2

    # grep
    result = await registry.execute(
        "grep",
        {"pattern": "def greet", "glob": "*.py"},
        ctx,
    )
    assert not result.error
    assert "hello.py" in result.output

    # events fired
    types = [t for t, _ in bus.history]
    assert EventType.AGENT_TOOL_CALL in types
    assert EventType.AGENT_TOOL_RESULT in types


@pytest.mark.asyncio
async def test_readonly_blocks_write(fixture_repo: Path) -> None:
    eng = PermissionEngine(
        PermissionsConfig(
            default="ask",
            trust_mode="readonly",
            rules=[PermissionRule(tool="read", agent="*", level="allow")],
        )
    )
    registry = create_default_registry(permission_engine=eng)
    ctx = ToolContext(workspace_root=fixture_repo, agent="coder")

    ok = await registry.execute("read", {"path": "README.md"}, ctx)
    assert not ok.error
    assert "Fixture" in ok.output

    blocked = await registry.execute(
        "write",
        {"path": "evil.py", "content": "hack"},
        ctx,
    )
    assert blocked.error
    assert "Permission denied" in blocked.output
    assert not (fixture_repo / "evil.py").exists()


@pytest.mark.asyncio
async def test_ask_handler(fixture_repo: Path) -> None:
    eng = PermissionEngine(
        PermissionsConfig(
            default="ask",
            trust_mode="interactive",
            rules=[PermissionRule(tool="bash", agent="coder", level="ask")],
        )
    )
    bus = EventBus()
    bus.enable_history(True)
    registry = create_default_registry(permission_engine=eng, event_bus=bus)
    ctx = ToolContext(workspace_root=fixture_repo, agent="coder", timeout=10.0)

    # No handler → deny
    denied = await registry.execute("bash", {"command": "echo hi"}, ctx)
    assert denied.error
    assert "Permission denied" in denied.output

    # Approve
    registry.set_ask_handler(lambda tool, agent, params: True)
    allowed = await registry.execute("bash", {"command": "echo aegis-ok"}, ctx)
    assert not allowed.error
    assert "aegis-ok" in allowed.output.replace("\r", "")

    perm_events = [t for t, _ in bus.history if t.startswith("permission.")]
    assert EventType.PERMISSION_REQUEST in perm_events
    assert EventType.PERMISSION_RESPONSE in perm_events


@pytest.mark.asyncio
async def test_path_escape_blocked(fixture_repo: Path) -> None:
    eng = PermissionEngine(PermissionsConfig(default="allow", trust_mode="yolo", rules=[]))
    registry = create_default_registry(permission_engine=eng)
    ctx = ToolContext(workspace_root=fixture_repo, agent="coder")
    result = await registry.execute("read", {"path": "../outside.txt"}, ctx)
    assert result.error
    assert "escapes workspace" in result.output.lower() or "Permission" in result.output


@pytest.mark.asyncio
async def test_edit_ambiguous(fixture_repo: Path) -> None:
    (fixture_repo / "dup.txt").write_text("aa\naa\n", encoding="utf-8")
    eng = PermissionEngine(PermissionsConfig(default="allow", trust_mode="yolo", rules=[]))
    registry = create_default_registry(permission_engine=eng)
    ctx = ToolContext(workspace_root=fixture_repo, agent="coder")
    result = await registry.execute(
        "edit",
        {"path": "dup.txt", "old_string": "aa", "new_string": "bb"},
        ctx,
    )
    assert result.error
    assert "2 times" in result.output or "ambiguous" in result.output.lower()

    result = await registry.execute(
        "edit",
        {
            "path": "dup.txt",
            "old_string": "aa",
            "new_string": "bb",
            "replace_all": True,
        },
        ctx,
    )
    assert not result.error
    assert (fixture_repo / "dup.txt").read_text(encoding="utf-8") == "bb\nbb\n"


@pytest.mark.asyncio
async def test_invalid_params(fixture_repo: Path) -> None:
    eng = PermissionEngine(PermissionsConfig(default="allow", trust_mode="yolo", rules=[]))
    registry = create_default_registry(permission_engine=eng)
    ctx = ToolContext(workspace_root=fixture_repo, agent="coder")
    result = await registry.execute("read", {}, ctx)
    assert result.error
    assert "Invalid parameters" in result.output
