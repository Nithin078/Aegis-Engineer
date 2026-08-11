"""Event bus for decoupled agent ↔ client communication."""

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus

__all__ = ["EventBus", "EventType"]
