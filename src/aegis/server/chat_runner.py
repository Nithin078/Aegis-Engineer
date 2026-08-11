"""Run the agent loop and publish SSE-friendly events."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Any

from aegis.agents.chat import create_chat_agent
from aegis.agents.loop import agent_loop
from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.config.schema import PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.server.state import AppState
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry

_current_session_id: ContextVar[str | None] = ContextVar("aegis_session_id", default=None)


class SessionTaggedBus(EventBus):
    """EventBus that injects session_id from a ContextVar into every publish."""

    def __init__(self, inner: EventBus) -> None:
        super().__init__()
        self._inner = inner
        # Share subscriber storage with the app bus
        self._subscribers = inner._subscribers
        self._wildcard = inner._wildcard
        self._history = inner._history
        self._record_history = inner._record_history

    async def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        payload = dict(data or {})
        sid = _current_session_id.get()
        if sid is not None:
            payload.setdefault("session_id", sid)
        await self._inner.publish(event_type, payload)


async def run_chat(
    state: AppState,
    session_id: str,
    prompt: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Execute one chat turn; returns summary dict for workflow.complete."""
    config = state.config
    session = state.sessions.get(session_id)
    model_name = model or session.model or config.provider.model
    provider_name = provider or session.provider or config.provider.default
    root = (workspace or state.workspace).resolve()

    mode = (
        config.permissions.trust_mode
        if config.permissions.trust_mode != "interactive"
        else "yolo"
    )
    perm_config = PermissionsConfig(
        default=config.permissions.default,
        trust_mode=mode,  # type: ignore[arg-type]
        rules=config.permissions.rules,
    )
    engine = PermissionEngine(perm_config)
    bus: EventBus = SessionTaggedBus(state.bus)
    registry = create_default_registry(permission_engine=engine, event_bus=bus)

    agent = create_chat_agent(
        model=model_name,
        max_iterations=config.agents.max_iterations,
        tool_timeout=config.agents.tool_timeout,
    )
    llm = state.make_provider(provider_name)
    ctx = ToolContext(
        workspace_root=root,
        agent=agent.name,
        event_bus=bus,
        timeout=agent.tool_timeout,
    )

    state.sessions.add_message(session_id, "user", prompt)

    token = _current_session_id.set(session_id)

    async def on_text(delta: str) -> None:
        await bus.publish(
            "agent.token",
            {"agent": agent.name, "delta": delta, "session_id": session_id},
        )

    try:
        result = await agent_loop(
            agent=agent,
            task=prompt,
            provider=llm,
            tools=registry,
            ctx=ctx,
            model=model_name,
            event_bus=bus,
            on_text=on_text,
        )
    finally:
        _current_session_id.reset(token)

    state.sessions.add_message(
        session_id,
        "assistant",
        result.output or "",
        tokens=result.total_tokens or None,
        cost_usd=result.cost_usd or None,
    )

    summary = {
        "session_id": session_id,
        "output": result.output,
        "iterations": result.iterations,
        "error": result.error,
        "tokens": result.total_tokens,
        "cost_usd": result.cost_usd,
        "tool_calls": result.tool_calls,
    }
    event_name = "workflow.complete" if not result.error else EventType.AGENT_ERROR
    await bus.publish(event_name, summary)
    return summary
