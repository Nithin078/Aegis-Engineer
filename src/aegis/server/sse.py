"""SSE helpers and session event fan-out."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from aegis.server.state import AppState


def format_sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    """Return a dict suitable for sse-starlette EventSourceResponse."""
    return {"event": event, "data": json.dumps(data, default=str)}


async def subscribe_session(
    state: AppState,
    session_id: str,
) -> tuple[asyncio.Queue[dict[str, str] | None], Any]:
    """Subscribe to events for a session. Returns (queue, unsubscribe)."""
    queue: asyncio.Queue[dict[str, str] | None] = asyncio.Queue()

    async def _handler(event_type: str, data: dict[str, Any]) -> None:
        # Only forward events tagged with this session (or untagged global)
        sid = data.get("session_id")
        if sid is not None and sid != session_id:
            return
        await queue.put(format_sse(event_type, {**data, "session_id": session_id}))

    state.bus.subscribe("*", _handler)
    state.event_subscribers.setdefault(session_id, []).append(queue)

    def unsubscribe() -> None:
        state.bus.unsubscribe("*", _handler)
        subs = state.event_subscribers.get(session_id, [])
        if queue in subs:
            subs.remove(queue)

    return queue, unsubscribe


async def queue_to_sse(
    queue: asyncio.Queue[dict[str, str] | None],
    *,
    unsubscribe: Any,
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE events from a queue until None sentinel."""
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        if callable(unsubscribe):
            unsubscribe()
