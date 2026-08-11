"""Models for documentation coverage and planning."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SurfaceKind(StrEnum):
    PACKAGE = "package"
    CLI = "cli"
    ROUTE = "route"
    MODULE = "module"


class DocSurface(BaseModel):
    """A documentable unit of the public surface."""

    kind: SurfaceKind
    id: str  # e.g. aegis.quality, aegis test, GET /health
    path: str | None = None  # source path if known
    description: str = ""


class DocGapKind(StrEnum):
    UNDOCUMENTED = "undocumented"
    STALE = "stale"
    MISSING_FILE = "missing_file"


class DocGap(BaseModel):
    kind: DocGapKind
    surface_id: str | None = None
    detail: str
    suggested_file: str | None = None


class DocActionKind(StrEnum):
    CREATE = "create"
    UPDATE = "update"


class DocAction(BaseModel):
    kind: DocActionKind
    target_path: str  # relative path e.g. docs/CLI.md
    topic: str
    reason: str
    content: str = ""  # filled by generator
    sources: list[str] = Field(default_factory=list)


class DocReport(BaseModel):
    workspace: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    surfaces: list[DocSurface] = Field(default_factory=list)
    documented_ids: list[str] = Field(default_factory=list)
    gaps: list[DocGap] = Field(default_factory=list)
    actions: list[DocAction] = Field(default_factory=list)
    coverage: float = 0.0  # 0..1
    stale_count: int = 0
    undocumented_count: int = 0
    written_files: list[str] = Field(default_factory=list)
    proposed_files: list[str] = Field(default_factory=list)
    report_path: str | None = None
    applied: bool = False
    check_only: bool = False

    def passes_check(self, min_coverage: float = 0.0, allow_stale: bool = False) -> bool:
        if self.coverage < min_coverage:
            return False
        if not allow_stale and self.stale_count > 0:
            return False
        # missing required topic files count as gaps
        missing = [g for g in self.gaps if g.kind is DocGapKind.MISSING_FILE]
        if missing:
            return False
        return True

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "created_at": self.created_at.isoformat(),
            "coverage": round(self.coverage, 4),
            "surfaces": len(self.surfaces),
            "documented": len(self.documented_ids),
            "undocumented_count": self.undocumented_count,
            "stale_count": self.stale_count,
            "gaps": len(self.gaps),
            "actions": len(self.actions),
            "written_files": self.written_files,
            "proposed_files": self.proposed_files,
            "report_path": self.report_path,
            "applied": self.applied,
        }
