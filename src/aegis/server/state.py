"""Application state shared across routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aegis.bus.pubsub import EventBus
from aegis.config.schema import AegisConfig
from aegis.providers.base import LLMProvider
from aegis.session.manager import SessionManager

ProviderFactory = Callable[[AegisConfig, str | None], LLMProvider]


@dataclass
class AppState:
    """Mutable server state attached to the Starlette app."""

    config: AegisConfig
    sessions: SessionManager
    workspace: Path
    bus: EventBus = field(default_factory=EventBus)
    # session_id → list of asyncio.Queue subscribers for live events
    event_subscribers: dict[str, list[Any]] = field(default_factory=dict)
    provider_factory: ProviderFactory | None = None

    def make_provider(self, provider_name: str | None = None) -> LLMProvider:
        if self.provider_factory is not None:
            return self.provider_factory(self.config, provider_name)
        from aegis.providers.factory import create_provider

        return create_provider(self.config, provider_name=provider_name)
