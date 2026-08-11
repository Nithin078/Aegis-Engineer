"""Shell command execution tool."""

from __future__ import annotations

import asyncio
import os

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult


class BashParams(BaseModel):
    command: str = Field(description="Shell command to execute")
    cwd: str | None = Field(
        default=None,
        description="Working directory relative to workspace (default: workspace root)",
    )
    timeout: float | None = Field(
        default=None,
        ge=0.1,
        description="Timeout in seconds (defaults to tool context timeout)",
    )


class BashTool(ToolDefinition):
    name = "bash"
    description = "Execute a shell command in the workspace (with timeout)."
    parameters = BashParams
    permissions = ["shell"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, BashParams)
        cwd = ctx.workspace_root
        if params.cwd:
            cwd = ctx.resolve_path(params.cwd)
            if not cwd.is_dir():
                return ToolResult(
                    output=f"Working directory not found: {params.cwd}",
                    title="invalid cwd",
                    error=True,
                    metadata={"error_type": "not_found"},
                )

        timeout = params.timeout if params.timeout is not None else ctx.timeout
        env = os.environ.copy()

        try:
            process = await asyncio.create_subprocess_shell(
                params.command,
                cwd=str(cwd),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                return ToolResult(
                    output=f"Command timed out after {timeout}s: {params.command}",
                    title="timeout",
                    error=True,
                    metadata={"error_type": "timeout", "timeout": timeout},
                )
        except OSError as exc:
            return ToolResult(
                output=f"Failed to start command: {exc}",
                title="spawn error",
                error=True,
                metadata={"error_type": "spawn_error"},
            )

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        exit_code = process.returncode if process.returncode is not None else -1

        parts: list[str] = []
        if stdout:
            parts.append(stdout.rstrip())
        if stderr:
            parts.append(f"[stderr]\n{stderr.rstrip()}")
        parts.append(f"[exit_code={exit_code}]")
        output = "\n".join(parts)

        max_chars = 50_000
        truncated = False
        if len(output) > max_chars:
            output = output[:max_chars] + "\n...[truncated]"
            truncated = True

        return ToolResult(
            output=output,
            title=f"bash: {params.command[:60]}",
            error=exit_code != 0,
            metadata={
                "exit_code": exit_code,
                "command": params.command,
                "truncated": truncated,
            },
        )
