"""Tool registration, lookup, and gated execution."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.permissions.engine import PermissionDecision, PermissionEngine
from aegis.tools.base import ToolContext, ToolDefinition, ToolResult
from aegis.tools.bash import BashTool
from aegis.tools.codesearch import CodeSearchTool
from aegis.tools.edit import EditTool
from aegis.tools.glob_tool import GlobTool
from aegis.tools.graph_query import GraphQueryTool
from aegis.tools.grep import GrepTool
from aegis.tools.read import ReadTool
from aegis.tools.webfetch import WebFetchTool
from aegis.tools.write import WriteTool

AskHandler = Callable[[str, str, dict[str, Any]], Awaitable[bool] | bool]


class ToolRegistry:
    """Registry of tools with permission checks and event publishing."""

    def __init__(
        self,
        permission_engine: PermissionEngine | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self.permission_engine = permission_engine or PermissionEngine()
        self.event_bus = event_bus or EventBus()
        self._ask_handler: AskHandler | None = None

    def set_ask_handler(self, handler: AskHandler | None) -> None:
        """Set callback for permission level ``ask`` (returns True to allow)."""
        self._ask_handler = handler

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def list_for_agent(self, agent_permissions: list[str] | None = None) -> list[ToolDefinition]:
        """Return tools whose capability tags are subset of agent_permissions.

        If agent_permissions is None, return all tools (filtering is via engine).
        """
        if agent_permissions is None:
            return self.list_tools()
        allowed: list[ToolDefinition] = []
        for tool in self._tools.values():
            if all(p in agent_permissions for p in tool.permissions):
                allowed.append(tool)
        return allowed

    def llm_schemas(self, agent_permissions: list[str] | None = None) -> list[dict[str, Any]]:
        return [t.to_llm_schema() for t in self.list_for_agent(agent_permissions)]

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        ctx: ToolContext,
    ) -> ToolResult:
        """Check permissions, publish events, execute tool with timeout."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                output=f"Unknown tool: {tool_name}",
                title="unknown tool",
                error=True,
                metadata={"error_type": "unknown_tool"},
            )

        # Prefer context bus if provided
        bus = ctx.event_bus or self.event_bus
        agent = ctx.agent

        # Plugin: tool.execute.before may rewrite params
        try:
            from aegis.plugins.hooks import get_hooks

            params = await get_hooks().run_tool_before(tool_name, params, agent)
        except Exception:  # noqa: BLE001
            pass

        await bus.publish(
            EventType.AGENT_TOOL_CALL,
            {"tool": tool_name, "params": params, "agent": agent},
        )

        decision = self.permission_engine.resolve(tool_name, agent, tool.permissions)
        allowed = await self._apply_decision(decision, tool_name, agent, params, bus)
        if not allowed:
            result = ToolResult(
                output=f"Permission denied for tool '{tool_name}' (agent={agent})",
                title="permission denied",
                error=True,
                metadata={
                    "error_type": "permission_denied",
                    "decision": decision.value,
                },
            )
            await bus.publish(
                EventType.AGENT_TOOL_RESULT,
                {
                    "tool": tool_name,
                    "agent": agent,
                    "error": True,
                    "output": result.output,
                    "duration_ms": 0,
                    "summary": result.output[:200],
                },
            )
            return result

        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                tool.run(params, ctx),
                timeout=ctx.timeout,
            )
        except TimeoutError:
            result = ToolResult(
                output=f"Tool {tool_name} timed out after {ctx.timeout}s",
                title="timeout",
                error=True,
                metadata={"error_type": "timeout"},
                duration_ms=ctx.timeout * 1000,
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not result.duration_ms:
            result.duration_ms = elapsed_ms

        try:
            from aegis.plugins.hooks import get_hooks

            maybe = await get_hooks().run_tool_after(tool_name, params, agent, result)
            if isinstance(maybe, ToolResult):
                result = maybe
        except Exception:  # noqa: BLE001
            pass

        await bus.publish(
            EventType.AGENT_TOOL_RESULT,
            {
                "tool": tool_name,
                "agent": agent,
                "error": result.error,
                "output": result.output[:2000],
                "duration_ms": result.duration_ms or elapsed_ms,
                "summary": (result.title or result.output)[:200],
                "metadata": result.metadata,
            },
        )
        return result

    async def _apply_decision(
        self,
        decision: PermissionDecision,
        tool_name: str,
        agent: str,
        params: dict[str, Any],
        bus: EventBus,
    ) -> bool:
        if decision is PermissionDecision.ALLOW:
            return True
        if decision is PermissionDecision.DENY:
            return False

        # ASK
        await bus.publish(
            EventType.PERMISSION_REQUEST,
            {"tool": tool_name, "agent": agent, "params": params},
        )
        approved = False
        if self._ask_handler is not None:
            outcome = self._ask_handler(tool_name, agent, params)
            if inspect.isawaitable(outcome):
                approved = bool(await outcome)
            else:
                approved = bool(outcome)

        await bus.publish(
            EventType.PERMISSION_RESPONSE,
            {"tool": tool_name, "agent": agent, "approved": approved},
        )
        return approved


def create_default_registry(
    permission_engine: PermissionEngine | None = None,
    event_bus: EventBus | None = None,
) -> ToolRegistry:
    """Build a registry with the core Phase-2 tools."""
    registry = ToolRegistry(permission_engine=permission_engine, event_bus=event_bus)
    for tool in (
        ReadTool(),
        WriteTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        BashTool(),
        GraphQueryTool(),
        CodeSearchTool(),
        WebFetchTool(),
    ):
        registry.register(tool)
    return registry
