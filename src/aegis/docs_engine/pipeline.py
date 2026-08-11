"""End-to-end documentation pipeline."""

from __future__ import annotations

from pathlib import Path

from aegis.docs_engine.coverage import build_coverage_report
from aegis.docs_engine.models import DocReport
from aegis.docs_engine.planner import plan_actions
from aegis.docs_engine.report import write_doc_report
from aegis.docs_engine.state import hash_sources, save_state
from aegis.docs_engine.writer import write_actions


def run_document(
    workspace: Path,
    *,
    apply: bool = False,
    check_only: bool = False,
    min_coverage: float = 0.0,
    allow_stale: bool = True,
    report_path: Path | None = None,
    refresh_all: bool = True,
) -> DocReport:
    """Analyze docs vs code; optionally write templates and report.

    Default (no flags): write **proposed** docs under ``docs/_proposed/``.
    ``--apply``: write real ``docs/*.md`` files.
    ``--check``: no file writes (except report under .aegis/reports).
    """
    root = workspace.resolve()
    report = build_coverage_report(root)
    report.check_only = check_only

    actions = plan_actions(root, report)
    report.actions = actions

    if not check_only:
        write_actions(root, report, actions, apply=apply)
    else:
        report.applied = False

    write_doc_report(report, root, report_path)

    # Persist state for drift tracking
    sources = [s.path for s in report.surfaces if s.path]
    sources += ["README.md", "docs/CLI.md", "docs/API.md", "docs/ARCHITECTURE.md"]
    save_state(
        root,
        report.to_summary_dict(),
        hash_sources(root, [s for s in sources if s]),
    )

    return report
