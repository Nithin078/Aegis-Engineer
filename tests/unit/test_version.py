"""Tests for version reporting."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from aegis import __version__
from aegis.cli.main import app

runner = CliRunner()


def test_package_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])


def test_version_command_text() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "aegis-engineer" in result.stdout


def test_version_command_json() -> None:
    result = runner.invoke(app, ["version", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["name"] == "aegis-engineer"
    assert data["version"] == __version__
    assert "python" in data
    assert "platform" in data


def test_global_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_module_main_importable() -> None:
    """`python -m aegis` entry exists."""
    import importlib

    mod = importlib.import_module("aegis.__main__")
    assert hasattr(mod, "app")
