"""Shared types for LLM providers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class ToolCallDelta(BaseModel):
    """Partial or complete tool call from the model."""

    id: str = ""
    name: str = ""
    arguments: str = ""  # JSON string (may accumulate across stream chunks)
    index: int = 0


class ChatChunk(BaseModel):
    """Single streamed chunk from a chat completion."""

    delta: str | None = None
    tool_call: ToolCallDelta | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    cost_usd: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Aggregated non-streaming style response collected from chunks."""

    content: str = ""
    tool_calls: list[ToolCallDelta] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0
