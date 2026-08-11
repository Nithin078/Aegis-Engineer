"""graph_query tool — agents query repository intelligence."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class GraphQueryParams(BaseModel):
    op: str = Field(
        description=(
            "Operation: callers | callees | definitions | importers | imports | "
            "subclasses | bases | dependencies | impact | search | hybrid"
        )
    )
    target: str = Field(
        description=(
            "Symbol, module, search text, or file:line for impact "
            "(e.g. format_name, util.format_name, src/app.py:10-20). "
            "For dependencies op, target may be empty."
        ),
        default="",
    )


class GraphQueryTool(ToolDefinition):
    name = "graph_query"
    description = (
        "Query repository intelligence: who calls a function, definitions, "
        "imports, inheritance (subclasses/bases), external dependencies, "
        "impact analysis, keyword or hybrid search."
    )
    parameters = GraphQueryParams
    permissions = ["read"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, GraphQueryParams)
        try:
            from aegis.intelligence.engine import IntelligenceEngine
        except ImportError as exc:
            return ToolResult(
                output=f"Intelligence engine unavailable: {exc}",
                error=True,
            )

        root = ctx.workspace_root
        eng = IntelligenceEngine(root)
        if not eng.index:
            eng.build()
        result = eng.graph_query(params.op, params.target)

        import json

        text = json.dumps(result, indent=2, default=str)
        if len(text) > 40_000:
            text = text[:40_000] + "\n...[truncated]"
        return ToolResult(
            output=text,
            title=f"graph_query {params.op} {params.target}",
            metadata={
                "op": params.op,
                "target": params.target,
                "count": len(result.get("results") or [])
                if isinstance(result.get("results"), list)
                else None,
            },
            error=bool(result.get("error")),
        )
