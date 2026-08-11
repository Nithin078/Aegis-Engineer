"""Tool system — typed, permission-gated actions for agents."""

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult
from aegis.tools.registry import ToolRegistry, create_default_registry

__all__ = [
    "ToolContext",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    "create_default_registry",
]
