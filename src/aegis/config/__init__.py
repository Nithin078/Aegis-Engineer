"""Configuration system for Aegis Engineer."""

from aegis.config.env import load_env
from aegis.config.loader import (
    get_config_dir,
    get_db_path,
    load_config,
    set_config_value,
    unset_config_value,
)
from aegis.config.schema import AegisConfig

__all__ = [
    "AegisConfig",
    "get_config_dir",
    "get_db_path",
    "load_config",
    "load_env",
    "set_config_value",
    "unset_config_value",
]
