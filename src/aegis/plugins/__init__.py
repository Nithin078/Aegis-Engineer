"""Plugin hooks and MCP integration."""

from aegis.plugins.hooks import HookRegistry, get_hooks, set_hooks
from aegis.plugins.mcp_client import MCPClient, MCPError, MCPToolBridge

__all__ = [
    "HookRegistry",
    "MCPClient",
    "MCPError",
    "MCPToolBridge",
    "get_hooks",
    "set_hooks",
]
