"""Plan create/update documentation actions from coverage gaps."""

from __future__ import annotations

from pathlib import Path

from aegis.docs_engine.models import DocAction, DocActionKind, DocReport, SurfaceKind
from aegis.docs_engine.templates import (
    render_api_md,
    render_architecture_md,
    render_changelog_snippet,
    render_cli_md,
    render_gaps_md,
)


def plan_actions(workspace: Path, report: DocReport) -> list[DocAction]:
    """Build deterministic doc actions (templates only — no LLM)."""
    root = workspace.resolve()
    actions: list[DocAction] = []
    surfaces = report.surfaces

    actions.append(
        DocAction(
            kind=DocActionKind.CREATE
            if not (root / "docs" / "GAPS.md").is_file()
            else DocActionKind.UPDATE,
            target_path="docs/GAPS.md",
            topic="gaps",
            reason="Documentation coverage gaps",
            content=render_gaps_md(report),
            sources=["coverage"],
        )
    )

    actions.append(
        DocAction(
            kind=DocActionKind.CREATE
            if not (root / "docs" / "CLI.md").is_file()
            else DocActionKind.UPDATE,
            target_path="docs/CLI.md",
            topic="cli",
            reason="CLI command reference from inventory",
            content=render_cli_md(surfaces, root),
            sources=[s.path for s in surfaces if s.kind is SurfaceKind.CLI and s.path],
        )
    )

    actions.append(
        DocAction(
            kind=DocActionKind.CREATE
            if not (root / "docs" / "API.md").is_file()
            else DocActionKind.UPDATE,
            target_path="docs/API.md",
            topic="api",
            reason="HTTP API routes from server inventory",
            content=render_api_md(surfaces),
            sources=[s.path for s in surfaces if s.kind is SurfaceKind.ROUTE and s.path],
        )
    )

    actions.append(
        DocAction(
            kind=DocActionKind.CREATE
            if not (root / "docs" / "ARCHITECTURE.md").is_file()
            else DocActionKind.UPDATE,
            target_path="docs/ARCHITECTURE.md",
            topic="architecture",
            reason="Package map from source inventory",
            content=render_architecture_md(surfaces, root),
            sources=[s.path for s in surfaces if s.kind is SurfaceKind.PACKAGE and s.path],
        )
    )

    topics = [a.topic for a in actions if a.topic not in {"gaps", "changelog"}]
    actions.append(
        DocAction(
            kind=DocActionKind.UPDATE
            if (root / "docs" / "CHANGELOG.aegis.md").is_file()
            else DocActionKind.CREATE,
            target_path="docs/CHANGELOG.aegis.md",
            topic="changelog",
            reason="Record documentation run",
            content=render_changelog_snippet(report, topics),
            sources=[],
        )
    )

    return actions
