"""Phase 11: plugin hooks + MCP client skeleton."""

from __future__ import annotations

import pytest

from aegis.plugins.hooks import (
    SYSTEM_PROMPT_TRANSFORM,
    TOOL_EXECUTE_BEFORE,
    HookRegistry,
    get_hooks,
    set_hooks,
)
from aegis.plugins.mcp_client import MCPClient, MCPToolBridge, mock_transport
from aegis.tools.base import ToolContext, ToolResult
from aegis.tools.registry import create_default_registry


@pytest.mark.asyncio
async def test_prompt_transform_hook() -> None:
    hooks = HookRegistry()

    def add_footer(agent: str, prompt: str) -> str:
        return prompt + f"\n# agent={agent}"

    hooks.on(SYSTEM_PROMPT_TRANSFORM, add_footer)
    out = await hooks.transform_system_prompt("coder", "You are helpful.")
    assert "agent=coder" in out


@pytest.mark.asyncio
async def test_tool_before_hook_rewrites_params(tmp_path) -> None:
    hooks = HookRegistry()

    def force_path(tool: str, params: dict, agent: str) -> dict:
        if tool == "read":
            return {**params, "path": "forced.txt"}
        return params

    hooks.on(TOOL_EXECUTE_BEFORE, force_path)
    set_hooks(hooks)
    try:
        (tmp_path / "forced.txt").write_text("hello", encoding="utf-8")
        (tmp_path / "other.txt").write_text("nope", encoding="utf-8")
        reg = create_default_registry()
        ctx = ToolContext(workspace_root=tmp_path, agent="tester")
        result = await reg.execute("read", {"path": "other.txt"}, ctx)
        assert not result.error
        assert "hello" in result.output
    finally:
        set_hooks(None)
        get_hooks().clear()


def test_mcp_client_list_and_call() -> None:
    def tools_list(_params: dict) -> dict:
        return {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo text",
                    "inputSchema": {"type": "object"},
                }
            ]
        }

    def tools_call(params: dict) -> dict:
        args = params.get("arguments") or {}
        return {"content": [{"type": "text", "text": f"echo:{args.get('msg', '')}"}]}

    client = MCPClient(
        transport=mock_transport(
            {
                "initialize": lambda _p: {"protocolVersion": "2024-11-05"},
                "tools/list": tools_list,
                "tools/call": tools_call,
            }
        )
    )
    tools = client.list_tools()
    assert tools[0]["name"] == "echo"
    result = client.call_tool("echo", {"msg": "hi"})
    assert "echo:hi" in str(result)


@pytest.mark.asyncio
async def test_mcp_bridge_registers(tmp_path) -> None:
    from aegis.config.schema import PermissionsConfig
    from aegis.permissions.engine import PermissionEngine

    client = MCPClient(
        transport=mock_transport(
            {
                "initialize": lambda _p: {},
                "tools/list": lambda _p: {
                    "tools": [{"name": "ping", "description": "Ping"}]
                },
                "tools/call": lambda p: {
                    "content": [{"type": "text", "text": "pong"}]
                },
            }
        )
    )
    eng = PermissionEngine(PermissionsConfig(default="allow", trust_mode="yolo"))
    reg = create_default_registry(permission_engine=eng)
    bridge = MCPToolBridge(client)
    names = bridge.register_all(reg)
    assert "mcp_ping" in names
    ctx = ToolContext(workspace_root=tmp_path, agent="tester")
    result = await reg.execute("mcp_ping", {"arguments": {}}, ctx)
    assert isinstance(result, ToolResult)
    assert "pong" in result.output
