"""Regex content search tool."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".aegis",
}

_BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".exe",
    ".dll",
    ".so",
    ".pyc",
    ".pyo",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


class GrepParams(BaseModel):
    pattern: str = Field(description="Regular expression pattern")
    path: str = Field(default=".", description="File or directory to search")
    glob: str | None = Field(default=None, description="Optional file glob filter, e.g. *.py")
    case_insensitive: bool = Field(default=False, description="Case-insensitive search")
    max_matches: int = Field(default=100, ge=1, le=1000, description="Max match lines")


class GrepTool(ToolDefinition):
    name = "grep"
    description = "Search file contents with a regular expression."
    parameters = GrepParams
    permissions = ["read"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, GrepParams)
        root = ctx.resolve_path(params.path)
        if not root.exists():
            return ToolResult(
                output=f"Path not found: {params.path}",
                title="not found",
                error=True,
                metadata={"error_type": "not_found"},
            )

        flags = re.IGNORECASE if params.case_insensitive else 0
        try:
            regex = re.compile(params.pattern, flags)
        except re.error as exc:
            return ToolResult(
                output=f"Invalid regex: {exc}",
                title="invalid regex",
                error=True,
                metadata={"error_type": "invalid_regex"},
            )

        files = _iter_files(root, params.glob)
        matches: list[str] = []
        workspace = ctx.workspace_root.resolve()
        for file_path in files:
            if len(matches) >= params.max_matches:
                break
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            try:
                rel_s = file_path.resolve().relative_to(workspace).as_posix()
            except ValueError:
                rel_s = str(file_path)

            for i, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    matches.append(f"{rel_s}:{i}:{line}")
                    if len(matches) >= params.max_matches:
                        break

        output = "\n".join(matches) if matches else "(no matches)"
        return ToolResult(
            output=output,
            title=f"grep {params.pattern}",
            metadata={
                "pattern": params.pattern,
                "match_count": len(matches),
                "capped": len(matches) >= params.max_matches,
            },
        )


def _iter_files(root: Path, glob_filter: str | None) -> list[Path]:
    if root.is_file():
        return [root]

    results: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _BINARY_EXTENSIONS:
            continue
        if glob_filter is not None:
            if not (
                fnmatch.fnmatch(path.name, glob_filter)
                or fnmatch.fnmatch(path.as_posix(), glob_filter)
            ):
                continue
        results.append(path)
    return results
