"""Minimal plugin hook system."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

# Hook names
TOOL_EXECUTE_BEFORE = "tool.execute.before"
TOOL_EXECUTE_AFTER = "tool.execute.after"
SYSTEM_PROMPT_TRANSFORM = "system.prompt.transform"


class HookRegistry:
    """In-process hooks for tools and prompts."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Any]]] = {
            TOOL_EXECUTE_BEFORE: [],
            TOOL_EXECUTE_AFTER: [],
            SYSTEM_PROMPT_TRANSFORM: [],
        }

    def on(self, name: str, fn: Callable[..., Any]) -> None:
        if name not in self._hooks:
            self._hooks[name] = []
        self._hooks[name].append(fn)

    def clear(self, name: str | None = None) -> None:
        if name is None:
            for k in self._hooks:
                self._hooks[k].clear()
        elif name in self._hooks:
            self._hooks[name].clear()

    def list_hooks(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._hooks.items()}

    async def run_tool_before(
        self, tool: str, params: dict[str, Any], agent: str
    ) -> dict[str, Any]:
        """Return possibly modified params."""
        current = dict(params)
        for fn in self._hooks.get(TOOL_EXECUTE_BEFORE, []):
            result = fn(tool, current, agent)
            if hasattr(result, "__await__"):
                result = await result  # type: ignore[misc]
            if isinstance(result, dict):
                current = result
        return current

    async def run_tool_after(
        self, tool: str, params: dict[str, Any], agent: str, result: Any
    ) -> Any:
        current = result
        for fn in self._hooks.get(TOOL_EXECUTE_AFTER, []):
            out = fn(tool, params, agent, current)
            if hasattr(out, "__await__"):
                out = await out  # type: ignore[misc]
            if out is not None:
                current = out
        return current

    async def transform_system_prompt(self, agent: str, prompt: str) -> str:
        current = prompt
        for fn in self._hooks.get(SYSTEM_PROMPT_TRANSFORM, []):
            out = fn(agent, current)
            if hasattr(out, "__await__"):
                out = await out  # type: ignore[misc]
            if isinstance(out, str) and out:
                current = out
        return current


_hooks_var: ContextVar[HookRegistry | None] = ContextVar("aegis_hooks", default=None)
_default_hooks = HookRegistry()


def get_hooks() -> HookRegistry:
    return _hooks_var.get() or _default_hooks


def set_hooks(hooks: HookRegistry | None) -> None:
    _hooks_var.set(hooks)
