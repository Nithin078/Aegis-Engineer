"""Inventory public code surface: packages, CLI commands, HTTP routes."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from aegis.docs_engine.models import DocSurface, SurfaceKind

_ROUTE_RE = re.compile(
    r'Route\(\s*["\']([^"\']+)["\']\s*,\s*[^,]+,\s*methods\s*=\s*\[([^\]]+)\]',
    re.MULTILINE,
)
_METHOD_RE = re.compile(r'["\']([A-Z]+)["\']')


def inventory_packages(workspace: Path) -> list[DocSurface]:
    """Top-level packages under src/<project>/ or src/aegis/."""
    root = workspace.resolve()
    surfaces: list[DocSurface] = []
    src = root / "src"
    if not src.is_dir():
        # fallback: package at root
        for p in sorted(root.iterdir()):
            if p.is_dir() and (p / "__init__.py").is_file() and not p.name.startswith("."):
                surfaces.append(
                    DocSurface(
                        kind=SurfaceKind.PACKAGE,
                        id=p.name,
                        path=str(p.relative_to(root).as_posix()),
                        description=f"Python package {p.name}",
                    )
                )
        return surfaces

    # Prefer src/aegis style: one dist package with subpackages
    for child in sorted(src.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / "__init__.py").is_file():
            continue
        # root package
        surfaces.append(
            DocSurface(
                kind=SurfaceKind.PACKAGE,
                id=child.name,
                path=str(child.relative_to(root).as_posix()),
                description=f"Top-level package {child.name}",
            )
        )
        # subpackages one level
        for sub in sorted(child.iterdir()):
            if sub.is_dir() and (sub / "__init__.py").is_file() and not sub.name.startswith("_"):
                surfaces.append(
                    DocSurface(
                        kind=SurfaceKind.PACKAGE,
                        id=f"{child.name}.{sub.name}",
                        path=str(sub.relative_to(root).as_posix()),
                        description=f"Subpackage {child.name}.{sub.name}",
                    )
                )
    return surfaces


def inventory_cli_commands(workspace: Path) -> list[DocSurface]:
    """Discover CLI commands by parsing cli/main.py and commands/*.py names."""
    root = workspace.resolve()
    surfaces: list[DocSurface] = []
    # Known entry: src/aegis/cli/main.py
    candidates = [
        root / "src" / "aegis" / "cli" / "main.py",
        root / "aegis" / "cli" / "main.py",
    ]
    main_py = next((p for p in candidates if p.is_file()), None)
    commands: set[str] = set()

    if main_py:
        text = main_py.read_text(encoding="utf-8", errors="replace")
        # app.command("name")
        for m in re.finditer(r'\.command\(\s*["\']([a-zA-Z0-9_-]+)["\']', text):
            commands.add(m.group(1))
        # app.add_typer(..., name="test")
        for m in re.finditer(r'add_typer\([^)]*name\s*=\s*["\']([a-zA-Z0-9_-]+)["\']', text):
            commands.add(m.group(1))
        # Default launch without subcommand is implied
        commands.add("(default TUI)")

        cmd_dir = main_py.parent / "commands"
        if cmd_dir.is_dir():
            for f in sorted(cmd_dir.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                # map file names to likely commands
                stem = f.stem
                if stem in {"test_cmd", "test"}:
                    commands.add("test")
                elif stem == "main":
                    continue
                else:
                    # serve, run, push, tui, doctor, version, config, session, document
                    commands.add(stem.replace("_", "-") if "_" in stem else stem)

    # Always document core if present in tree
    for name in ("version", "doctor", "run", "serve", "tui", "config", "session", "test", "push"):
        # only add if we found any CLI at all
        if commands:
            commands.add(name)

    for name in sorted(commands):
        surfaces.append(
            DocSurface(
                kind=SurfaceKind.CLI,
                id=f"aegis {name}" if not name.startswith("(") else name,
                path=str(main_py.relative_to(root).as_posix()) if main_py else None,
                description=f"CLI command: {name}",
            )
        )
    return surfaces


def inventory_routes(workspace: Path) -> list[DocSurface]:
    """Static scan for Starlette Route(...) definitions."""
    root = workspace.resolve()
    surfaces: list[DocSurface] = []
    search_dirs = [
        root / "src" / "aegis" / "server",
        root / "src" / "aegis" / "server" / "routes",
        root / "aegis" / "server",
    ]
    files: list[Path] = []
    for d in search_dirs:
        if d.is_dir():
            files.extend(d.rglob("*.py"))
    # also app.py
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = f.relative_to(root).as_posix()
        for m in _ROUTE_RE.finditer(text):
            path = m.group(1)
            methods_raw = m.group(2)
            methods = _METHOD_RE.findall(methods_raw) or ["GET"]
            for method in methods:
                surfaces.append(
                    DocSurface(
                        kind=SurfaceKind.ROUTE,
                        id=f"{method} {path}",
                        path=rel,
                        description=f"HTTP {method} {path}",
                    )
                )
        # Fallback simpler: Route("/x"
        if not list(_ROUTE_RE.finditer(text)):
            for m in re.finditer(r'Route\(\s*["\']([^"\']+)["\']', text):
                path = m.group(1)
                surfaces.append(
                    DocSurface(
                        kind=SurfaceKind.ROUTE,
                        id=f"ROUTE {path}",
                        path=rel,
                        description=f"HTTP route {path}",
                    )
                )
    # dedupe by id
    seen: set[str] = set()
    unique: list[DocSurface] = []
    for s in surfaces:
        if s.id in seen:
            continue
        seen.add(s.id)
        unique.append(s)
    return unique


def inventory_all(workspace: Path) -> list[DocSurface]:
    surfaces = (
        inventory_packages(workspace)
        + inventory_cli_commands(workspace)
        + inventory_routes(workspace)
    )
    return surfaces


def public_module_names_from_ast(file_path: Path) -> list[str]:
    """Optional helper: top-level function/class names in a file."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names
