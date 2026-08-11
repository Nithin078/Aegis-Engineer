"""File pattern matching tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class GlobParams(BaseModel):
    pattern: str = Field(description="Glob pattern, e.g. **/*.py")
    path: str = Field(
        default=".",
        description="Directory relative to workspace root to search under",
    )


class GlobTool(ToolDefinition):
    name = "glob"
    description = "Find files matching a glob pattern under the workspace."
    parameters = GlobParams
    permissions = ["read"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, GlobParams)
        base = ctx.resolve_path(params.path)
        if not base.exists():
            return ToolResult(
                output=f"Path not found: {params.path}",
                title="not found",
                error=True,
                metadata={"error_type": "not_found"},
            )
        if base.is_file():
            base = base.parent

        matches: list[str] = []
        for match in sorted(base.glob(params.pattern)):
            if match.is_file():
                try:
                    rel = match.resolve().relative_to(ctx.workspace_root.resolve())
                    matches.append(rel.as_posix())
                except ValueError:
                    matches.append(str(match))

        max_results = 500
        truncated = len(matches) > max_results
        shown = matches[:max_results]
        output = "\n".join(shown) if shown else "(no matches)"
        if truncated:
            output += f"\n... truncated ({len(matches)} total)"

        return ToolResult(
            output=output,
            title=f"glob {params.pattern}",
            metadata={
                "pattern": params.pattern,
                "count": len(matches),
                "truncated": truncated,
            },
        )
