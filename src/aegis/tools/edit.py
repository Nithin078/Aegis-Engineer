"""Targeted string-replacement edit tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class EditParams(BaseModel):
    path: str = Field(description="File path relative to workspace root")
    old_string: str = Field(description="Exact text to find")
    new_string: str = Field(description="Replacement text")
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences (default: only one exact match)",
    )


class EditTool(ToolDefinition):
    name = "edit"
    description = (
        "Replace text in a file. By default old_string must appear exactly once; "
        "use replace_all to change every occurrence."
    )
    parameters = EditParams
    permissions = ["write"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, EditParams)
        path = ctx.resolve_path(params.path)
        if not path.is_file():
            return ToolResult(
                output=f"File not found: {params.path}",
                title="not found",
                error=True,
                metadata={"error_type": "not_found"},
            )

        original = path.read_text(encoding="utf-8")
        count = original.count(params.old_string)
        if count == 0:
            return ToolResult(
                output=f"old_string not found in {params.path}",
                title="no match",
                error=True,
                metadata={"error_type": "no_match", "path": params.path},
            )
        if count > 1 and not params.replace_all:
            return ToolResult(
                output=(
                    f"old_string found {count} times in {params.path}; "
                    "provide more context or set replace_all=true"
                ),
                title="ambiguous match",
                error=True,
                metadata={"error_type": "ambiguous_match", "count": count},
            )

        if params.replace_all:
            updated = original.replace(params.old_string, params.new_string)
            replacements = count
        else:
            updated = original.replace(params.old_string, params.new_string, 1)
            replacements = 1

        path.write_text(updated, encoding="utf-8")
        return ToolResult(
            output=f"Edited {params.path} ({replacements} replacement(s))",
            title=f"Edited {params.path}",
            metadata={"path": params.path, "replacements": replacements},
        )
