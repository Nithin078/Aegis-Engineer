"""Debug tool execution route."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from aegis.config.schema import PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.server.deps import get_state
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry


async def execute_tool(request: Request) -> JSONResponse:
    state = get_state(request)
    body: dict[str, Any] = await request.json()
    tool_name = body.get("tool")
    params = body.get("params") or {}
    if not tool_name or not isinstance(tool_name, str):
        return JSONResponse({"error": "tool is required"}, status_code=400)
    if not isinstance(params, dict):
        return JSONResponse({"error": "params must be an object"}, status_code=400)

    mode = (
        state.config.permissions.trust_mode
        if state.config.permissions.trust_mode != "interactive"
        else "yolo"
    )
    engine = PermissionEngine(
        PermissionsConfig(
            default=state.config.permissions.default,
            trust_mode=mode,  # type: ignore[arg-type]
            rules=state.config.permissions.rules,
        )
    )
    registry = create_default_registry(permission_engine=engine, event_bus=state.bus)
    ctx = ToolContext(
        workspace_root=state.workspace,
        agent=body.get("agent") or "debug",
        event_bus=state.bus,
        timeout=state.config.agents.tool_timeout,
    )
    result = await registry.execute(tool_name, params, ctx)
    return JSONResponse(
        {
            "output": result.output,
            "title": result.title,
            "metadata": result.metadata,
            "error": result.error,
            "duration_ms": result.duration_ms,
        },
        status_code=200 if not result.error else 400,
    )
