"""Tool definition base types."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    from aegis.bus.pubsub import EventBus


class ToolResult(BaseModel):
    """Structured result returned from a tool execution."""

    output: str
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    error: bool = False
    duration_ms: float = 0.0


@dataclass
class ToolContext:
    """Runtime context passed to every tool execution."""

    workspace_root: Path
    agent: str = "default"
    event_bus: EventBus | None = None
    timeout: float = 30.0
    extra: dict[str, Any] = field(default_factory=dict)

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve a path relative to workspace and ensure it stays inside."""
        root = self.workspace_root.resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PermissionError(
                f"Path escapes workspace root: {path} (root={root})"
            ) from exc
        return resolved


class ToolDefinition(ABC):
    """Base class for all tools.

    Subclasses set ``name``, ``description``, ``parameters`` (Pydantic model),
    and ``permissions`` (capability tags checked by the permission engine).
    """

    name: str
    description: str
    parameters: type[BaseModel]
    permissions: list[str] = ["read"]  # capability tags, e.g. read/write/shell

    @abstractmethod
    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        """Run the tool with validated parameters."""

    async def run(self, raw_params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """Validate parameters, execute, and stamp duration."""
        started = time.perf_counter()
        try:
            params = self.parameters.model_validate(raw_params)
        except ValidationError as exc:
            return ToolResult(
                output=f"Invalid parameters for tool {self.name}: {exc}",
                title="validation error",
                error=True,
                metadata={"error_type": "validation_error"},
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        try:
            result = await self.execute(params, ctx)
        except PermissionError as exc:
            result = ToolResult(
                output=str(exc),
                title="permission error",
                error=True,
                metadata={"error_type": "path_permission"},
            )
        except Exception as exc:  # noqa: BLE001 — surface tool failures to agent
            result = ToolResult(
                output=f"Tool {self.name} failed: {exc}",
                title="execution error",
                error=True,
                metadata={
                    "error_type": "execution_error",
                    "exception": type(exc).__name__,
                },
            )

        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    def to_llm_schema(self) -> dict[str, Any]:
        """OpenAI-style function schema for LLM tool calling."""
        from aegis.tools.schema_utils import sanitize_json_schema

        schema = sanitize_json_schema(self.parameters.model_json_schema())
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }
