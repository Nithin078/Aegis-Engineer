"""codesearch tool — hybrid semantic/keyword code search."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class CodeSearchParams(BaseModel):
    query: str = Field(description="Natural language or keyword query over the codebase")
    limit: int = Field(default=20, ge=1, le=50, description="Max results")


class CodeSearchTool(ToolDefinition):
    name = "codesearch"
    description = (
        "Hybrid search over repository symbols (semantic TF-IDF + keywords + graph). "
        "Use for 'find authentication code' style questions. "
        "Builds intelligence index if missing."
    )
    parameters = CodeSearchParams
    permissions = ["read"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, CodeSearchParams)
        from aegis.intelligence.engine import IntelligenceEngine

        eng = IntelligenceEngine(ctx.workspace_root)
        if not eng.index:
            eng.build()
        hits = eng.hybrid_search(params.query, limit=params.limit)
        payload = {"query": params.query, "count": len(hits), "results": hits}
        text = json.dumps(payload, indent=2, default=str)
        if len(text) > 40_000:
            text = text[:40_000] + "\n...[truncated]"
        return ToolResult(
            output=text,
            title=f"codesearch: {params.query[:60]}",
            metadata={"count": len(hits)},
        )
