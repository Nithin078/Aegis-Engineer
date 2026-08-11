"""Tests for the agent loop with a mock provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis.agents.base import Agent
from aegis.agents.chat import create_chat_agent
from aegis.agents.loop import agent_loop
from aegis.bus.pubsub import EventBus
from aegis.config.schema import PermissionRule, PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.providers.mock import MockProvider, text_response, tool_then_text
from aegis.providers.types import ChatChunk, TokenUsage, ToolCallDelta
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Hello Fixture\n\nDetails here.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("VALUE = 42\n", encoding="utf-8")
    return tmp_path


def _registry(bus: EventBus | None = None) -> object:
    eng = PermissionEngine(
        PermissionsConfig(
            default="allow",
            trust_mode="yolo",
            rules=[PermissionRule(tool="*", agent="*", level="allow")],
        )
    )
    return create_default_registry(permission_engine=eng, event_bus=bus or EventBus())


@pytest.mark.asyncio
async def test_agent_loop_text_only(workspace: Path) -> None:
    bus = EventBus()
    bus.enable_history(True)
    provider = MockProvider(responses=[text_response("All good.")])
    agent = create_chat_agent(max_iterations=5)
    ctx = ToolContext(workspace_root=workspace, agent=agent.name, event_bus=bus)
    result = await agent_loop(
        agent=agent,
        task="Say hi",
        provider=provider,
        tools=_registry(bus),  # type: ignore[arg-type]
        ctx=ctx,
        model="mock",
        event_bus=bus,
    )
    assert result.error is None
    assert result.output == "All good."
    assert result.iterations == 1
    assert result.total_tokens > 0
    assert any(t == "agent.start" for t, _ in bus.history)
    assert any(t == "agent.done" for t, _ in bus.history)


@pytest.mark.asyncio
async def test_agent_loop_with_tool(workspace: Path) -> None:
    first, second = tool_then_text(
        "read",
        json.dumps({"path": "README.md"}),
        "README describes Hello Fixture.",
    )
    provider = MockProvider(responses=[first, second])
    bus = EventBus()
    bus.enable_history(True)
    agent = create_chat_agent(max_iterations=5)
    ctx = ToolContext(workspace_root=workspace, agent=agent.name, event_bus=bus, timeout=10)
    texts: list[str] = []

    async def on_text(delta: str) -> None:
        texts.append(delta)

    result = await agent_loop(
        agent=agent,
        task="What does the README say?",
        provider=provider,
        tools=_registry(bus),  # type: ignore[arg-type]
        ctx=ctx,
        model="mock",
        event_bus=bus,
        on_text=on_text,
    )
    assert result.error is None
    assert "Hello Fixture" in result.output or "README" in result.output
    assert result.tool_calls == 1
    assert result.iterations == 2
    # Tool result was fed back to the provider as a tool message
    assert len(provider.calls) == 2
    second_msgs = provider.calls[1]["messages"]
    assert any(m.get("role") == "tool" for m in second_msgs)
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    assert "Hello Fixture" in tool_msg["content"]
    assert any(t == "agent.tool_call" for t, _ in bus.history)
    assert "".join(texts) == result.output


@pytest.mark.asyncio
async def test_max_iterations(workspace: Path) -> None:
    # Always request a tool → hit max iterations
    def forever_tool(
        messages: list,
        model: str,
        tools: list | None,
    ) -> list[ChatChunk]:
        return [
            ChatChunk(
                tool_call=ToolCallDelta(
                    id="call_x",
                    name="read",
                    arguments=json.dumps({"path": "README.md"}),
                    index=0,
                ),
                finish_reason="tool_calls",
            ),
            ChatChunk(usage=TokenUsage(input_tokens=5, output_tokens=5, total_tokens=10)),
        ]

    provider = MockProvider(responder=forever_tool)
    agent = Agent(
        name="chat",
        system_prompt="test",
        max_iterations=3,
        tool_timeout=5,
        permissions=["read", "write", "shell"],
    )
    ctx = ToolContext(workspace_root=workspace, agent=agent.name, timeout=5)
    result = await agent_loop(
        agent=agent,
        task="loop",
        provider=provider,
        tools=_registry(),  # type: ignore[arg-type]
        ctx=ctx,
        model="mock",
    )
    assert result.error == "max_iterations_exceeded"
    assert result.iterations == 3
    assert result.tool_calls == 3
