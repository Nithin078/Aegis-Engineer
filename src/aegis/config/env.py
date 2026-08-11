"""Load environment variables from ``.env`` files."""

from __future__ import annotations

from pathlib import Path

_loaded = False


def user_env_path() -> Path:
    """Path to the global user ``.env`` (shared across all projects)."""
    import os

    config_dir = os.environ.get("AEGIS_CONFIG_DIR")
    if config_dir:
        return Path(config_dir).expanduser().resolve() / ".env"
    return (Path.home() / ".config" / "aegis" / ".env").resolve()


def load_env(*, project_dir: Path | None = None, force: bool = False) -> list[Path]:
    """Load ``.env`` files into ``os.environ`` (does not override existing vars).

    Search order (later files only fill keys that are still missing):

    1. ``<project>/.env`` — optional per-repo settings (cwd or project_dir)
    2. ``~/.config/aegis/.env`` — **global** keys (works from any directory)

    Real shell environment variables always win (never overwritten).

    Put your Groq/OpenAI key in the global file so ``aegis`` works in every
    project folder without copying ``.env`` around.
    """
    global _loaded
    if _loaded and not force:
        return []

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        _loaded = True
        return []

    loaded: list[Path] = []
    root = (project_dir or Path.cwd()).resolve()

    # Project first so its keys take precedence over the global file.
    # (load_dotenv override=False → first write wins for each key.)
    for path in (root / ".env", user_env_path()):
        if path.is_file():
            load_dotenv(path, override=False)
            loaded.append(path)

    _loaded = True
    return loaded


def reset_env_loader() -> None:
    """Test helper: allow loading again."""
    global _loaded
    _loaded = False
