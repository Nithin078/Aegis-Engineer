"""Default configuration values."""

from __future__ import annotations

from aegis.config.schema import AegisConfig


def default_config() -> AegisConfig:
    """Return a fresh default configuration instance."""
    return AegisConfig()
