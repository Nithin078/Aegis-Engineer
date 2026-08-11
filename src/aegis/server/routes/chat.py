"""Chat endpoint with SSE streaming."""

from __future__ import annotations

import asyncio
from typing import Any

from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import JSONResponse

from aegis.server.chat_runner import run_chat
from aegis.server.deps import get_state
from aegis.server.sse import queue_to_sse, subscribe_session
from aegis.session.manager import SessionNotFoundError


async def chat_session(request: Request) -> EventSourceResponse | JSONResponse:
    state = get_state(request)
    session_id = request.path_params["session_id"]

    try:
        state.sessions.get(session_id)
    except SessionNotFoundError:
        return JSONResponse({"error": "session not found"}, status_code=404)

    body: dict[str, Any] = await request.json()
    prompt = body.get("prompt") or body.get("message")
    if not prompt or not isinstance(prompt, str):
        return JSONResponse({"error": "prompt is required"}, status_code=400)

    stream = body.get("stream", True)
    model = body.get("model")
    provider = body.get("provider")

    if not stream:
        summary = await run_chat(
            state,
            session_id,
            prompt,
            model=model,
            provider=provider,
        )
        status = 200 if not summary.get("error") else 500
        return JSONResponse(summary, status_code=status)

    queue, unsubscribe = await subscribe_session(state, session_id)

    async def _run() -> None:
        try:
            await run_chat(
                state,
                session_id,
                prompt,
                model=model,
                provider=provider,
            )
        except Exception as exc:  # noqa: BLE001
            await state.bus.publish(
                "agent.error",
                {"session_id": session_id, "error": str(exc)},
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run())

    async def event_generator() -> Any:
        try:
            async for item in queue_to_sse(queue, unsubscribe=unsubscribe):
                yield item
        finally:
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_generator())
