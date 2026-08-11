"""Deterministic mock provider for tests (no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from aegis.providers.base import LLMProvider
from aegis.providers.types import ChatChunk, TokenUsage, ToolCallDelta

# (messages, model, tools) -> list of ChatChunk batches per "turn"
Responder = Callable[
    [list[dict[str, Any]], str, list[dict[str, Any]] | None],
    list[ChatChunk],
]


class MockProvider(LLMProvider):
    """Returns scripted responses, optionally advancing through a queue."""

    name = "mock"

    def __init__(
        self,
        responses: list[list[ChatChunk]] | None = None,
        responder: Responder | None = None,
    ) -> None:
        self._queue = list(responses or [])
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    def enqueue(self, chunks: list[ChatChunk]) -> None:
        self._queue.append(chunks)

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
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "tools": tools,
                "stream": stream,
            }
        )
        if self._responder is not None:
            chunks = self._responder(messages, model, tools)
        elif self._queue:
            chunks = self._queue.pop(0)
        else:
            chunks = [
                ChatChunk(
                    delta="(mock: no response queued)",
                    finish_reason="stop",
                    usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                    cost_usd=0.0,
                )
            ]

        for chunk in chunks:
            yield chunk


def text_response(text: str, *, input_tokens: int = 20, output_tokens: int = 10) -> list[ChatChunk]:
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
    return [
        ChatChunk(delta=text, finish_reason="stop"),
        ChatChunk(usage=usage, cost_usd=0.0001, finish_reason="stop"),
    ]


def tool_then_text(
    tool_name: str,
    arguments: str,
    final_text: str,
    *,
    tool_id: str = "call_1",
) -> tuple[list[ChatChunk], list[ChatChunk]]:
    """Two turns: first requests a tool, second returns final text."""
    first = [
        ChatChunk(
            tool_call=ToolCallDelta(
                id=tool_id,
                name=tool_name,
                arguments=arguments,
                index=0,
            ),
            finish_reason="tool_calls",
        ),
        ChatChunk(
            usage=TokenUsage(input_tokens=30, output_tokens=15, total_tokens=45),
            cost_usd=0.0002,
        ),
    ]
    second = text_response(final_text, input_tokens=40, output_tokens=20)
    return first, second
