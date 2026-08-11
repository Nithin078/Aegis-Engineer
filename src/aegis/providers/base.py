"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from aegis.providers.types import ChatChunk, TokenUsage


class LLMProvider(ABC):
    """Unified interface for chat completions across vendors."""

    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Stream (or yield once) chat completion chunks."""
        # pragma: no cover - abstract
        if False:  # make this an async generator type
            yield ChatChunk()

    async def count_tokens(
        self,
        messages: list[dict[str, Any]],
        model: str,
    ) -> TokenUsage:
        """Best-effort token estimate. Default: character heuristic."""
        text = ""
        for msg in messages:
            content = msg.get("content") or ""
            if isinstance(content, str):
                text += content
        # Rough ~4 chars/token
        estimate = max(1, len(text) // 4)
        return TokenUsage(input_tokens=estimate, output_tokens=0, total_tokens=estimate)
