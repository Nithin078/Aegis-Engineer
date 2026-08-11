"""Event type constants used across the system."""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    """Well-known event names published on the event bus."""

    # Agent lifecycle
    AGENT_START = "agent.start"
    AGENT_THINKING = "agent.thinking"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_TOOL_RESULT = "agent.tool_result"
    AGENT_DONE = "agent.done"
    AGENT_ERROR = "agent.error"
    AGENT_ESCALATION = "agent.escalation"

    # Permissions
    PERMISSION_REQUEST = "permission.request"
    PERMISSION_RESPONSE = "permission.response"

    # Sessions
    SESSION_UPDATE = "session.update"
    MESSAGE_ADD = "message.add"

    # Logging
    LOG_INFO = "log.info"
    LOG_ERROR = "log.error"
    LOG_DEBUG = "log.debug"
