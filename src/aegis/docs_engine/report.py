"""Markdown report for documentation coverage."""

from __future__ import annotations

from pathlib import Path

from aegis.docs_engine.models import DocReport


def render_doc_report_md(report: DocReport) -> str:
    lines = [
        "# Aegis Documentation Report",
        "",
        f"**Workspace:** `{report.workspace}`  ",
        f"**When:** {report.created_at.isoformat()}  ",
        f"**Coverage:** **{report.coverage:.1%}** "
        f"({len(report.documented_ids)}/{len(report.surfaces)} surfaces)  ",
        f"**Undocumented:** {report.undocumented_count}  ",
        f"**Stale:** {report.stale_count}  ",
        f"**Mode:** {'apply' if report.applied else ('check' if report.check_only else 'propose')}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Surfaces | {len(report.surfaces)} |",
        f"| Documented | {len(report.documented_ids)} |",
        f"| Coverage | {report.coverage:.1%} |",
        f"| Gaps | {len(report.gaps)} |",
        f"| Planned actions | {len(report.actions)} |",
        "",
        "## Gaps",
        "",
    ]
    if not report.gaps:
        lines.append("_None — nice work._")
    else:
        for g in report.gaps[:50]:
            sid = f" `{g.surface_id}`" if g.surface_id else ""
            lines.append(f"- **{g.kind.value}**{sid}: {g.detail}")
        if len(report.gaps) > 50:
            lines.append(f"- _…and {len(report.gaps) - 50} more_")
    lines.extend(["", "## Actions", ""])
    if not report.actions:
        lines.append("_No write actions._")
    else:
        for a in report.actions:
            lines.append(f"- **{a.kind.value}** `{a.target_path}` — {a.reason}")
    if report.written_files:
        lines.extend(["", "### Written", ""])
        for w in report.written_files:
            lines.append(f"- `{w}`")
    if report.proposed_files:
        lines.extend(["", "### Proposed (use `--apply` to write for real)", ""])
        for w in report.proposed_files:
            lines.append(f"- `{w}`")
    lines.extend(
        [
            "",
            "## Next steps",
            "",
            "```bash",
            "aegis document --check     # CI: fail on gaps / low coverage",
            "aegis document             # write proposals under docs/_proposed/",
            "aegis document --apply     # write docs/CLI.md, API.md, …",
            "aegis test --docs          # quality gate includes doc coverage",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_doc_report(report: DocReport, workspace: Path, path: Path | None = None) -> Path:
    out = path or (workspace.resolve() / ".aegis" / "reports" / "docs-latest.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_doc_report_md(report), encoding="utf-8")
    report.report_path = str(out)
    return out
