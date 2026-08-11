"""Retry helpers for LLM calls."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable


class LLMError(Exception):
    """Base error for provider failures."""


class RateLimitError(LLMError):
    """Provider rate limited the request."""


class LLMExhaustedError(LLMError):
    """All retry attempts failed."""


async def with_retries[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (RateLimitError, TimeoutError),
) -> T:
    """Retry an async callable with exponential backoff."""
    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except retry_on as exc:
            last_error = exc
            if attempt >= max_retries - 1:
                break
            await asyncio.sleep(base_delay * (2**attempt))
    raise LLMExhaustedError(f"All {max_retries} attempts failed: {last_error}") from last_error


async def collect_stream[T](stream: AsyncIterator[T]) -> list[T]:
    items: list[T] = []
    async for item in stream:
        items.append(item)
    return items
