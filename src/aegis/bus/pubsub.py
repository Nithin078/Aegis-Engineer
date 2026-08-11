"""Async publish/subscribe event bus."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

EventCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class EventBus:
    """In-process async event bus.

    Subscribers may be sync or async callables. Publish awaits async
    handlers and runs sync handlers in the current task.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)
        self._wildcard: list[EventCallback] = []
        self._history: list[tuple[str, dict[str, Any]]] = []
        self._record_history: bool = False

    def enable_history(self, enabled: bool = True) -> None:
        """When enabled, store published events for tests/debugging."""
        self._record_history = enabled
        if not enabled:
            self._history.clear()

    @property
    def history(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._history)

    def subscribe(self, event_type: str, callback: EventCallback) -> None:
        """Subscribe to a specific event type, or ``*`` for all events."""
        if event_type == "*":
            self._wildcard.append(callback)
        else:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: EventCallback) -> None:
        if event_type == "*":
            if callback in self._wildcard:
                self._wildcard.remove(callback)
            return
        handlers = self._subscribers.get(event_type)
        if handlers and callback in handlers:
            handlers.remove(callback)

    async def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        payload = dict(data or {})
        if self._record_history:
            self._history.append((event_type, payload))

        handlers = list(self._subscribers.get(event_type, [])) + list(self._wildcard)
        for callback in handlers:
            result = callback(event_type, payload)
            if inspect.isawaitable(result):
                await result

    def clear(self) -> None:
        self._subscribers.clear()
        self._wildcard.clear()
        self._history.clear()
