"""Long-lived SSE event stream."""

from __future__ import annotations

from typing import Any

from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import JSONResponse

from aegis.server.deps import get_state
from aegis.server.sse import format_sse, queue_to_sse, subscribe_session
from aegis.session.manager import SessionNotFoundError


async def event_stream(request: Request) -> EventSourceResponse | JSONResponse:
    state = get_state(request)
    session_id = request.query_params.get("session_id")
    if not session_id:
        return JSONResponse({"error": "session_id query param required"}, status_code=400)

    try:
        state.sessions.get(session_id)
    except SessionNotFoundError:
        return JSONResponse({"error": "session not found"}, status_code=404)

    queue, unsubscribe = await subscribe_session(state, session_id)

    # Immediate hello so clients know the stream is live
    await queue.put(
        format_sse("log.info", {"message": "subscribed", "session_id": session_id})
    )

    async def generator() -> Any:
        async for item in queue_to_sse(queue, unsubscribe=unsubscribe):
            if await request.is_disconnected():
                break
            yield item

    return EventSourceResponse(generator())
