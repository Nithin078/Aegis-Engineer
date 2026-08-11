"""Minimal MCP (Model Context Protocol) client skeleton.

Supports a simple JSON-RPC transport interface so tests can inject a mock
without requiring the full MCP SDK. Real stdio servers can be wired later.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class MCPError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.code = code


Transport = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class MCPClient:
    """JSON-RPC style MCP client over a pluggable transport."""

    transport: Transport
    name: str = "mcp"
    _id: int = 0
    _tools: list[dict[str, Any]] = field(default_factory=list)
    initialized: bool = False

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        resp = self.transport(request)
        if not isinstance(resp, dict):
            raise MCPError("Invalid MCP response type")
        if "error" in resp and resp["error"]:
            err = resp["error"]
            if isinstance(err, dict):
                raise MCPError(str(err.get("message") or err), code=err.get("code"))
            raise MCPError(str(err))
        return resp.get("result")

    def initialize(self) -> dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "aegis-engineer", "version": "0.1.0"},
            },
        )
        self.initialized = True
        return result if isinstance(result, dict) else {}

    def list_tools(self) -> list[dict[str, Any]]:
        if not self.initialized:
            self.initialize()
        result = self._rpc("tools/list", {})
        tools = []
        if isinstance(result, dict):
            tools = list(result.get("tools") or [])
        elif isinstance(result, list):
            tools = result
        self._tools = [t for t in tools if isinstance(t, dict)]
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self.initialized:
            self.initialize()
        return self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )


class MCPToolParams(BaseModel):
    """Generic catch-all params for bridged MCP tools."""

    arguments: dict[str, Any] = Field(default_factory=dict)


@dataclass
class MCPToolBridge:
    """Register MCP tools into an Aegis ToolRegistry."""

    client: MCPClient
    prefix: str = "mcp_"

    def discover(self) -> list[ToolDefinition]:
        tools = self.client.list_tools()
        defs: list[ToolDefinition] = []
        for t in tools:
            name = str(t.get("name") or "tool")
            desc = str(t.get("description") or f"MCP tool {name}")
            defs.append(self._make_tool(name, desc, t.get("inputSchema") or {}))
        return defs

    def register_all(self, registry: Any) -> list[str]:
        names: list[str] = []
        for tool in self.discover():
            registry.register(tool)
            names.append(tool.name)
        return names

    def _make_tool(
        self, remote_name: str, description: str, _schema: dict[str, Any]
    ) -> ToolDefinition:
        client = self.client
        local_name = f"{self.prefix}{remote_name}"
        tool_description = description
        remote = remote_name

        class _MCPTool(ToolDefinition):
            name = local_name
            description = tool_description
            parameters = MCPToolParams
            permissions = ["read"]

            async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
                assert isinstance(params, MCPToolParams)
                try:
                    args = params.arguments or {}
                    result = client.call_tool(remote, args)
                    if isinstance(result, dict):
                        content = result.get("content")
                        if isinstance(content, list):
                            texts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    texts.append(str(block.get("text") or ""))
                                else:
                                    texts.append(json.dumps(block))
                            output = "\n".join(texts) if texts else json.dumps(result)
                        else:
                            output = json.dumps(result)
                    else:
                        output = str(result)
                    return ToolResult(output=output, title=f"mcp:{remote}")
                except MCPError as exc:
                    return ToolResult(
                        output=str(exc),
                        title="mcp error",
                        error=True,
                        metadata={"error_type": "mcp_error"},
                    )

        return _MCPTool()


def mock_transport(handlers: dict[str, Callable[[dict[str, Any]], Any]]) -> Transport:
    """Build a transport from method → result handlers (for tests)."""

    def _transport(request: dict[str, Any]) -> dict[str, Any]:
        method = str(request.get("method") or "")
        params = request.get("params") or {}
        req_id = request.get("id")
        if method not in handlers:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        try:
            result = handlers[method](params if isinstance(params, dict) else {})
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(exc)},
            }

    return _transport
