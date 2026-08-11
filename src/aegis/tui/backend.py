"""In-process agent backend for the TUI."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aegis.agents.chat import create_chat_agent
from aegis.agents.loop import agent_loop
from aegis.bus.pubsub import EventBus
from aegis.config.loader import get_db_path, load_config
from aegis.config.schema import PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.providers.factory import create_provider, provider_configured, resolve_api_key
from aegis.session.manager import SessionManager
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry

# Callbacks used by the UI
OnToken = Callable[[str], None]
OnEvent = Callable[[str, dict[str, Any]], None]
AskHandler = Callable[[str, str, dict[str, Any]], Awaitable[bool]]


class TuiBackend:
    """Runs chat turns in-process (same path as ``aegis run``)."""

    def __init__(
        self,
        *,
        workspace: Path,
        model: str | None = None,
        provider: str | None = None,
        trust_mode: str | None = None,
        ask_handler: AskHandler | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.config = load_config()
        self.provider_name = provider or self.config.provider.default
        self.model_name = model or self.config.provider.model
        self.trust_mode = trust_mode or self.config.permissions.trust_mode
        self.ask_handler = ask_handler
        self.session_mgr = SessionManager(get_db_path(self.config))
        self.session_id: str | None = None
        self.bus = EventBus()
        self._busy = False

    def ensure_api_key(self) -> tuple[bool, str]:
        if self.provider_name.lower() in {"ollama", "mock"}:
            return True, "ok"
        ok, detail = provider_configured(self.config)
        if ok:
            return True, detail
        key = resolve_api_key(self.provider_name, self.config.provider)
        if key:
            return True, "key present"
        return False, detail

    def create_session(self, title: str = "TUI session") -> str:
        session = self.session_mgr.create(
            title=title,
            model=self.model_name,
            provider=self.provider_name,
        )
        self.session_id = session.id
        return session.id

    async def chat(
        self,
        prompt: str,
        *,
        on_token: OnToken | None = None,
        on_event: OnEvent | None = None,
    ) -> dict[str, Any]:
        if self._busy:
            return {"error": "busy", "output": ""}
        self._busy = True
        try:
            return await self._chat_inner(prompt, on_token=on_token, on_event=on_event)
        finally:
            self._busy = False

    async def _chat_inner(
        self,
        prompt: str,
        *,
        on_token: OnToken | None,
        on_event: OnEvent | None,
    ) -> dict[str, Any]:
        if not self.session_id:
            self.create_session(title=prompt[:60] or "TUI session")

        mode = self.trust_mode
        # Interactive TUI keeps ask; yolo/readonly/ci as configured
        perm_config = PermissionsConfig(
            default=self.config.permissions.default,
            trust_mode=mode,  # type: ignore[arg-type]
            rules=self.config.permissions.rules,
        )
        engine = PermissionEngine(perm_config)
        registry = create_default_registry(
            permission_engine=engine,
            event_bus=self.bus,
        )
        if self.ask_handler is not None:
            registry.set_ask_handler(self.ask_handler)

        async def _bus_handler(event_type: str, data: dict[str, Any]) -> None:
            if on_event is not None:
                on_event(event_type, data)

        self.bus.subscribe("*", _bus_handler)

        agent = create_chat_agent(
            model=self.model_name,
            max_iterations=self.config.agents.max_iterations,
            tool_timeout=self.config.agents.tool_timeout,
        )
        llm = create_provider(self.config, provider_name=self.provider_name)
        ctx = ToolContext(
            workspace_root=self.workspace,
            agent=agent.name,
            event_bus=self.bus,
            timeout=agent.tool_timeout,
        )

        assert self.session_id is not None
        self.session_mgr.add_message(self.session_id, "user", prompt)

        def _on_text(delta: str) -> None:
            if on_token is not None:
                on_token(delta)

        try:
            result = await agent_loop(
                agent=agent,
                task=prompt,
                provider=llm,
                tools=registry,
                ctx=ctx,
                model=self.model_name,
                event_bus=self.bus,
                on_text=_on_text,
            )
        finally:
            self.bus.unsubscribe("*", _bus_handler)

        self.session_mgr.add_message(
            self.session_id,
            "assistant",
            result.output or "",
            tokens=result.total_tokens or None,
            cost_usd=result.cost_usd or None,
        )

        return {
            "session_id": self.session_id,
            "output": result.output,
            "error": result.error,
            "iterations": result.iterations,
            "tokens": result.total_tokens,
            "cost_usd": result.cost_usd,
            "tool_calls": result.tool_calls,
        }


class HttpTuiBackend:
    """Optional backend that talks to ``aegis serve`` over HTTP + SSE."""

    def __init__(self, base_url: str, *, workspace: Path | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.workspace = (workspace or Path.cwd()).resolve()
        self.session_id: str | None = None
        self.provider_name = "server"
        self.model_name = "server"
        self._busy = False

    def ensure_api_key(self) -> tuple[bool, str]:
        return True, "server mode (keys on server)"

    def create_session(self, title: str = "TUI session") -> str:
        import httpx

        r = httpx.post(
            f"{self.base_url}/session",
            json={"title": title},
            timeout=30.0,
        )
        r.raise_for_status()
        self.session_id = r.json()["id"]
        return self.session_id

    async def chat(
        self,
        prompt: str,
        *,
        on_token: OnToken | None = None,
        on_event: OnEvent | None = None,
    ) -> dict[str, Any]:
        import httpx

        if self._busy:
            return {"error": "busy", "output": ""}
        self._busy = True
        try:
            if not self.session_id:
                # create session async via thread
                await asyncio.to_thread(self.create_session, prompt[:60] or "TUI")

            assert self.session_id is not None
            output_parts: list[str] = []
            summary: dict[str, Any] = {"session_id": self.session_id}

            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/session/{self.session_id}/chat",
                    json={"prompt": prompt, "stream": True},
                ) as response:
                    response.raise_for_status()
                    event_name = "message"
                    async for line in response.aiter_lines():
                        if line.startswith("event:"):
                            event_name = line[6:].strip()
                        elif line.startswith("data:"):
                            raw = line[5:].strip()
                            try:
                                import json

                                data = json.loads(raw)
                            except json.JSONDecodeError:
                                data = {"raw": raw}
                            if on_event is not None:
                                on_event(event_name, data if isinstance(data, dict) else {})
                            if event_name == "agent.token" and isinstance(data, dict):
                                delta = data.get("delta") or ""
                                output_parts.append(str(delta))
                                if on_token is not None:
                                    on_token(str(delta))
                            if event_name in {"workflow.complete", "agent.done"}:
                                if isinstance(data, dict):
                                    summary.update(data)
                                    if data.get("output"):
                                        output_parts = [str(data["output"])]

            summary.setdefault("output", "".join(output_parts))
            return summary
        finally:
            self._busy = False
