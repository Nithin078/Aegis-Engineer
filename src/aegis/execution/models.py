"""Execution result models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """Result of a single local or sandboxed command."""

    command: list[str] = Field(default_factory=list)
    command_display: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    timed_out: bool = False
    backend: str = "local"  # local | docker

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        return ((self.stdout or "") + "\n" + (self.stderr or "")).strip()


class SandboxResult(BaseModel):
    """Docker (or local fallback) sandbox run."""

    backend: str  # docker | local_fallback
    exit_code: int = 0
    output: str = ""
    image: str | None = None
    error: str | None = None
    command: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.error


class PipelineStepResult(BaseModel):
    name: str
    skipped: bool = False
    result: CommandResult | None = None
    reason: str = ""


class PipelineResult(BaseModel):
    """Formatter → linter → tests pipeline outcome."""

    passed: bool = True
    steps: list[PipelineStepResult] = Field(default_factory=list)
    backend: str = "local"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def step(self, name: str) -> PipelineStepResult | None:
        for s in self.steps:
            if s.name == name:
                return s
        return None
