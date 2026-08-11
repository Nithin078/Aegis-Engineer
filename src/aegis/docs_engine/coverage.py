"""Match code surface against documentation references."""

from __future__ import annotations

from pathlib import Path

from aegis.docs_engine.inventory_code import inventory_all
from aegis.docs_engine.inventory_docs import inventory_doc_refs
from aegis.docs_engine.models import DocGap, DocGapKind, DocReport, DocSurface, SurfaceKind

# Topic files Aegis expects for a healthy docs set
REQUIRED_TOPIC_FILES = {
    "docs/CLI.md": "cli",
    "docs/API.md": "api",
    "docs/ARCHITECTURE.md": "architecture",
}


def _surface_documented(surface: DocSurface, refs: set[str], corpus: str) -> bool:
    """Heuristic: surface id or key tokens appear in docs."""
    sid = surface.id
    # direct
    if sid in refs:
        return True
    sid_l = sid.lower()
    if sid_l in corpus:
        return True

    if surface.kind is SurfaceKind.CLI:
        # "aegis test" or "test" command
        name = sid.replace("aegis ", "").strip()
        if f"aegis {name}" in corpus or f"`{name}`" in corpus:
            return True
        if name in refs or f"aegis {name}" in refs:
            return True

    if surface.kind is SurfaceKind.ROUTE:
        # "GET /health" or "/health"
        parts = sid.split(maxsplit=1)
        if len(parts) == 2:
            path = parts[1]
            if path in corpus or path in refs:
                return True

    if surface.kind is SurfaceKind.PACKAGE:
        # aegis.quality or quality package
        if surface.id in refs or surface.id.split(".")[-1] in refs:
            return True
        if surface.path and surface.path in corpus:
            return True
        if surface.id.lower() in corpus:
            return True

    return False


def _stale_refs(refs: set[str], surfaces: list[DocSurface]) -> list[DocGap]:
    """Doc mentions CLI commands that don't exist on the surface."""
    known_cli = {
        s.id.lower()
        for s in surfaces
        if s.kind is SurfaceKind.CLI
    }
    known_routes = {s.id for s in surfaces if s.kind is SurfaceKind.ROUTE}
    gaps: list[DocGap] = []
    for ref in sorted(refs):
        if ref.lower().startswith("aegis "):
            cmd = ref.lower()
            # ignore generic aegis mentions
            if cmd in {"aegis run", "aegis"}:
                continue
            if known_cli and cmd not in known_cli and not any(
                cmd.startswith(k) for k in known_cli
            ):
                # only flag if it looks like a specific subcommand we track
                rest = cmd.replace("aegis ", "", 1)
                if rest.isidentifier() or "-" in rest:
                    if not any(rest == k.replace("aegis ", "") for k in known_cli):
                        gaps.append(
                            DocGap(
                                kind=DocGapKind.STALE,
                                surface_id=ref,
                                detail=f"Docs mention `{ref}` but no matching CLI command found",
                            )
                        )
        if ref.startswith("GET ") or ref.startswith("POST "):
            if known_routes and ref not in known_routes:
                # soft: path-only match
                path = ref.split(maxsplit=1)[-1]
                if not any(path in r for r in known_routes):
                    gaps.append(
                        DocGap(
                            kind=DocGapKind.STALE,
                            surface_id=ref,
                            detail=f"Docs mention route `{ref}` not found in server routes",
                        )
                    )
    return gaps


def build_coverage_report(workspace: Path) -> DocReport:
    root = workspace.resolve()
    surfaces = inventory_all(root)
    doc_files, refs, corpus = inventory_doc_refs(root)

    documented: list[str] = []
    gaps: list[DocGap] = []

    for s in surfaces:
        if _surface_documented(s, refs, corpus):
            documented.append(s.id)
        else:
            gaps.append(
                DocGap(
                    kind=DocGapKind.UNDOCUMENTED,
                    surface_id=s.id,
                    detail=f"No documentation reference found for {s.kind.value} `{s.id}`",
                    suggested_file=_suggest_file(s),
                )
            )

    # required topic files
    for rel, topic in REQUIRED_TOPIC_FILES.items():
        if not (root / rel).is_file():
            gaps.append(
                DocGap(
                    kind=DocGapKind.MISSING_FILE,
                    detail=f"Missing topic file `{rel}`",
                    suggested_file=rel,
                    surface_id=topic,
                )
            )

    stale = _stale_refs(refs, surfaces)
    # limit stale noise
    gaps.extend(stale[:20])

    total = len(surfaces) or 1
    coverage = len(documented) / total
    undoc = sum(1 for g in gaps if g.kind is DocGapKind.UNDOCUMENTED)
    stale_n = sum(1 for g in gaps if g.kind is DocGapKind.STALE)

    return DocReport(
        workspace=str(root),
        surfaces=surfaces,
        documented_ids=documented,
        gaps=gaps,
        coverage=coverage,
        undocumented_count=undoc,
        stale_count=stale_n,
    )


def _suggest_file(surface: DocSurface) -> str:
    if surface.kind is SurfaceKind.CLI:
        return "docs/CLI.md"
    if surface.kind is SurfaceKind.ROUTE:
        return "docs/API.md"
    if surface.kind is SurfaceKind.PACKAGE:
        return "docs/ARCHITECTURE.md"
    return "docs/GAPS.md"
