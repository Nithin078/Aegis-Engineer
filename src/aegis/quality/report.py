"""Write Markdown and JSON quality gate reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aegis.quality.models import CheckStatus, GateReport, Verdict


def default_report_dir(workspace: Path) -> Path:
    return workspace.resolve() / ".aegis" / "reports"


def write_reports(
    report: GateReport,
    workspace: Path,
    *,
    report_path: Path | None = None,
) -> GateReport:
    """Write timestamped + latest markdown/json reports; update report paths."""
    out_dir = default_report_dir(workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if report_path is None:
        md_path = out_dir / f"test-report-{stamp}.md"
    else:
        md_path = report_path
        md_path.parent.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"

    md = render_markdown(report)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    payload = report.to_summary_dict()
    payload["report_md_path"] = str(md_path)
    payload["report_json_path"] = str(json_path)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    report.report_md_path = str(md_path)
    report.report_json_path = str(json_path)
    return report


def render_markdown(report: GateReport) -> str:
    lines: list[str] = [
        "# Aegis Quality Gate Report",
        "",
        f"**Workspace:** `{report.workspace}`  ",
        f"**When:** {report.created_at.isoformat()}  ",
        f"**Verdict:** **{report.verdict.value}**",
        "",
        "## Summary",
        "",
        "| Check | Status | Required | Detail |",
        "|-------|--------|----------|--------|",
    ]
    for c in report.checks:
        status = c.status.value.upper()
        req = "yes" if c.required else "no"
        detail = c.summary.replace("|", "\\|")
        lines.append(f"| {c.name} | {status} | {req} | {detail} |")

    lines.extend(["", "## Findings", ""])
    any_findings = False
    for c in report.checks:
        if not c.findings:
            continue
        any_findings = True
        lines.append(f"### {c.name}")
        lines.append("")
        for f in c.findings:
            loc = f" (`{f.location}`)" if f.location else ""
            lines.append(f"- **{f.severity}** — {f.message}{loc}")
            if f.detail:
                # fenced so secrets redactions stay readable
                lines.append("")
                lines.append("```")
                lines.append(f.detail[:2000])
                lines.append("```")
                lines.append("")
        lines.append("")

    if not any_findings:
        lines.append("_No findings._")
        lines.append("")

    lines.append("## Commands run")
    lines.append("")
    for c in report.checks:
        if c.command:
            lines.append(f"- **{c.name}:** `{c.command}`")
    if not any(c.command for c in report.checks):
        lines.append("_None._")
    lines.append("")

    lines.append("## Verdict")
    lines.append("")
    if report.verdict is Verdict.SAFE:
        lines.append(
            "✅ **All required checks passed.** Safe to push to GitHub "
            "(use `aegis push` or a pre-push hook)."
        )
    else:
        n = len(report.failed_required())
        lines.append(
            f"❌ **Not safe to push.** Fix {n} required failure(s) above, "
            "then re-run `aegis test`."
        )
    lines.append("")
    return "\n".join(lines)


def load_latest_json(workspace: Path) -> dict | None:
    path = default_report_dir(workspace) / "latest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def status_emoji(status: CheckStatus) -> str:
    return {
        CheckStatus.PASS: "✅",
        CheckStatus.FAIL: "❌",
        CheckStatus.SKIP: "⏭️",
        CheckStatus.ERROR: "💥",
    }.get(status, "·")
