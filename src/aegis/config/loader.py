"""Hierarchical configuration loading and persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aegis.config.defaults import default_config
from aegis.config.schema import (
    AegisConfig,
    parse_cli_value,
    set_nested,
    unset_nested,
)

# Environment variables that override loaded config.
_ENV_OVERRIDES: dict[str, str] = {
    "AEGIS_PROVIDER": "provider.default",
    "AEGIS_MODEL": "provider.model",
    "AEGIS_PERMISSION_MODE": "permissions.trust_mode",
    "AEGIS_SERVER_PORT": "server.port",
    "AEGIS_LOG_LEVEL": "observability.log_level",
}


def get_config_dir() -> Path:
    """Return the user config directory (overridable via AEGIS_CONFIG_DIR)."""
    override = os.environ.get("AEGIS_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".config" / "aegis").resolve()


def get_user_config_path() -> Path:
    return get_config_dir() / "config.json"


def get_project_config_paths(project_dir: Path | None = None) -> list[Path]:
    """Project-local config candidates, later paths win when both exist."""
    root = (project_dir or Path.cwd()).resolve()
    return [
        root / ".aegis.json",
        root / ".aegis" / "config.json",
    ]


def get_db_path(config: AegisConfig | None = None, project_dir: Path | None = None) -> Path:
    """Resolve SQLite database path.

    Precedence:
    1. AEGIS_DB_PATH env
    2. config.db_path
    3. <config_dir>/aegis.db
    """
    env_path = os.environ.get("AEGIS_DB_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    cfg = config or load_config(project_dir=project_dir)
    if cfg.db_path:
        return Path(cfg.db_path).expanduser().resolve()

    return get_config_dir() / "aegis.db"


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Drop schema annotation if present.
    data.pop("$schema", None)
    return data


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base (overlay wins)."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    for env_name, dotted_key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_name)
        if raw is None or raw == "":
            continue
        set_nested(result, dotted_key, parse_cli_value(raw))

    # Generic API key: AEGIS_API_KEY applies to the default provider when set.
    api_key = os.environ.get("AEGIS_API_KEY")
    if api_key:
        provider = result.get("provider", {})
        if not isinstance(provider, dict):
            provider = {}
            result["provider"] = provider
        default_provider = provider.get("default", "anthropic")
        api_keys = provider.get("api_keys", {})
        if not isinstance(api_keys, dict):
            api_keys = {}
        api_keys[str(default_provider)] = api_key
        provider["api_keys"] = api_keys

    return result


def load_config(
    project_dir: Path | None = None,
    *,
    user_config_path: Path | None = None,
    apply_env: bool = True,
) -> AegisConfig:
    """Load config: defaults < user file < project file < env vars."""
    merged: dict[str, Any] = default_config().model_dump(mode="json")

    user_path = user_config_path or get_user_config_path()
    merged = _deep_merge(merged, _read_json_file(user_path))

    for path in get_project_config_paths(project_dir):
        merged = _deep_merge(merged, _read_json_file(path))

    if apply_env:
        merged = _apply_env_overrides(merged)

    return AegisConfig.model_validate(merged)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def set_config_value(
    dotted_key: str,
    value: Any,
    *,
    project: bool = False,
    project_dir: Path | None = None,
    user_config_path: Path | None = None,
) -> Path:
    """Persist a config value. Returns the file path written."""
    if project:
        root = (project_dir or Path.cwd()).resolve()
        path = root / ".aegis" / "config.json"
    else:
        path = user_config_path or get_user_config_path()

    data = _read_json_file(path)
    if not isinstance(value, (dict, list, bool, int, float, type(None))):
        if isinstance(value, str):
            value = parse_cli_value(value)
    set_nested(data, dotted_key, value)

    # Validate the merge against full schema so bad keys fail early.
    trial = _deep_merge(default_config().model_dump(mode="json"), data)
    if project:
        # Also layer user config so project-only partial files still validate.
        defaults = default_config().model_dump(mode="json")
        user_data = _read_json_file(get_user_config_path())
        trial = _deep_merge(_deep_merge(defaults, user_data), data)
    AegisConfig.model_validate(trial)

    _write_json(path, data)
    return path


def unset_config_value(
    dotted_key: str,
    *,
    project: bool = False,
    project_dir: Path | None = None,
    user_config_path: Path | None = None,
) -> tuple[Path, bool]:
    """Remove a key from the target config file. Returns (path, removed)."""
    if project:
        root = (project_dir or Path.cwd()).resolve()
        path = root / ".aegis" / "config.json"
    else:
        path = user_config_path or get_user_config_path()

    data = _read_json_file(path)
    removed = unset_nested(data, dotted_key)
    if removed:
        _write_json(path, data)
    return path, removed
