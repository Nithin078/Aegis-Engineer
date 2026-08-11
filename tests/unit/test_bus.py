"""Tests for the event bus."""

from __future__ import annotations

import pytest

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus


@pytest.mark.asyncio
async def test_publish_subscribe() -> None:
    bus = EventBus()
    received: list[tuple[str, dict]] = []

    async def handler(event_type: str, data: dict) -> None:
        received.append((event_type, data))

    bus.subscribe(EventType.AGENT_TOOL_CALL, handler)
    await bus.publish(EventType.AGENT_TOOL_CALL, {"tool": "read"})
    assert len(received) == 1
    assert received[0][0] == EventType.AGENT_TOOL_CALL
    assert received[0][1]["tool"] == "read"


@pytest.mark.asyncio
async def test_wildcard_and_history() -> None:
    bus = EventBus()
    bus.enable_history(True)
    seen: list[str] = []

    def sync_handler(event_type: str, data: dict) -> None:
        seen.append(event_type)

    bus.subscribe("*", sync_handler)
    await bus.publish(EventType.LOG_INFO, {"msg": "hi"})
    await bus.publish(EventType.AGENT_DONE, {"ok": True})
    assert seen == [EventType.LOG_INFO, EventType.AGENT_DONE]
    assert len(bus.history) == 2


@pytest.mark.asyncio
async def test_unsubscribe() -> None:
    bus = EventBus()
    count = {"n": 0}

    async def handler(event_type: str, data: dict) -> None:
        count["n"] += 1

    bus.subscribe("x", handler)
    await bus.publish("x", {})
    bus.unsubscribe("x", handler)
    await bus.publish("x", {})
    assert count["n"] == 1
