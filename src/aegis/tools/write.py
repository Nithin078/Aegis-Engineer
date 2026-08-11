"""File write tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class WriteParams(BaseModel):
    path: str = Field(description="File path relative to workspace root")
    content: str = Field(description="Full file content to write")


class WriteTool(ToolDefinition):
    name = "write"
    description = "Create or overwrite a file with the given content."
    parameters = WriteParams
    permissions = ["write"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, WriteParams)
        path = ctx.resolve_path(params.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params.content, encoding="utf-8")
        return ToolResult(
            output=f"Wrote {len(params.content)} bytes to {params.path}",
            title=f"Wrote {params.path}",
            metadata={"path": params.path, "bytes": len(params.content.encode("utf-8"))},
        )
