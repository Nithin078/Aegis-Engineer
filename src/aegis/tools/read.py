"""File read tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class ReadParams(BaseModel):
    path: str = Field(description="File path relative to workspace root")
    offset: int = Field(default=1, ge=1, description="1-based start line")
    limit: int | None = Field(default=None, ge=1, description="Max lines to return")


class ReadTool(ToolDefinition):
    name = "read"
    description = "Read a file with optional line range support."
    parameters = ReadParams
    permissions = ["read"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, ReadParams)
        path = ctx.resolve_path(params.path)
        if not path.is_file():
            return ToolResult(
                output=f"File not found: {params.path}",
                title="not found",
                error=True,
                metadata={"error_type": "not_found", "path": params.path},
            )

        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = params.offset - 1
        end = len(lines) if params.limit is None else start + params.limit
        selected = lines[start:end]
        numbered = [f"{i + start + 1:>6}|{line}" for i, line in enumerate(selected)]
        output = "\n".join(numbered)
        return ToolResult(
            output=output,
            title=f"Read {params.path}",
            metadata={
                "path": params.path,
                "total_lines": len(lines),
                "start_line": params.offset,
                "end_line": min(end, len(lines)),
            },
        )
