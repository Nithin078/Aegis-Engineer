"""Base agent types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class Agent:
    """Configuration for a specialized agent."""

    name: str
    system_prompt: str
    model: str | None = None
    # Capability tags the agent is allowed to request (read/write/shell/…)
    permissions: list[str] = field(default_factory=lambda: ["read", "write", "shell"])
    max_iterations: int = 20
    tool_timeout: float = 30.0


class AgentResult(BaseModel):
    """Outcome of an agent_loop run."""

    output: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    iterations: int = 0
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0
