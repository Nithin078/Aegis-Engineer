"""Helpers for working with permission rule lists."""

from __future__ import annotations

from aegis.config.schema import PermissionRule, PermissionsConfig


def rules_from_dicts(items: list[dict[str, str]]) -> list[PermissionRule]:
    return [PermissionRule.model_validate(item) for item in items]


def with_trust_mode(config: PermissionsConfig, mode: str) -> PermissionsConfig:
    """Return a copy of config with a different trust mode."""
    return config.model_copy(update={"trust_mode": mode})
