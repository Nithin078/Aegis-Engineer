"""Persist and load session traces under .aegis/traces/."""

from __future__ import annotations

import json
from pathlib import Path

from aegis.observability.models import SessionTrace


def traces_dir(workspace: Path | str) -> Path:
    return Path(workspace).resolve() / ".aegis" / "traces"


def save_trace(trace: SessionTrace, workspace: Path | str) -> Path:
    out = traces_dir(workspace)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{trace.id}.json"
    path.write_text(
        trace.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    latest = out / "latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    # small index line
    index = out / "index.jsonl"
    with index.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "id": trace.id,
                    "workflow": trace.workflow,
                    "success": trace.success,
                    "started_at": trace.started_at.isoformat(),
                    "finished_at": (
                        trace.finished_at.isoformat() if trace.finished_at else None
                    ),
                    "totals": trace.totals,
                    "path": str(path),
                }
            )
            + "\n"
        )
    return path


def load_trace(trace_id: str, workspace: Path | str) -> SessionTrace | None:
    root = traces_dir(workspace)
    if trace_id in {"latest", "last"}:
        path = root / "latest.json"
    else:
        path = root / f"{trace_id}.json"
        if not path.is_file() and not trace_id.startswith("trace_"):
            path = root / f"trace_{trace_id}.json"
    if not path.is_file():
        # search by prefix
        matches = list(root.glob(f"*{trace_id}*.json"))
        matches = [m for m in matches if m.name != "latest.json"]
        if not matches:
            return None
        path = matches[0]
    try:
        return SessionTrace.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_traces(workspace: Path | str, *, limit: int = 20) -> list[dict]:
    root = traces_dir(workspace)
    index = root / "index.jsonl"
    rows: list[dict] = []
    if index.is_file():
        for line in index.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    else:
        for path in sorted(root.glob("trace_*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                rows.append(
                    {
                        "id": data.get("id"),
                        "workflow": data.get("workflow"),
                        "success": data.get("success"),
                        "totals": data.get("totals"),
                        "path": str(path),
                    }
                )
            except (OSError, json.JSONDecodeError):
                continue
    rows.reverse()  # oldest first in file; show newest first
    rows = list(reversed(rows))
    return rows[:limit]


def render_summary_md(trace: SessionTrace) -> str:
    trace.recompute_totals()
    lines = [
        f"# Trace `{trace.id}`",
        "",
        f"- **workflow:** {trace.workflow or '—'}",
        f"- **success:** {trace.success}",
        f"- **workspace:** `{trace.workspace}`",
        f"- **started:** {trace.started_at.isoformat()}",
        f"- **finished:** {trace.finished_at.isoformat() if trace.finished_at else '—'}",
        f"- **tokens:** {trace.totals.get('tokens', 0)}",
        f"- **cost_usd:** {trace.totals.get('cost_usd', 0)}",
        f"- **duration_ms:** {trace.totals.get('duration_ms', 0)}",
        f"- **tool_calls:** {trace.totals.get('tool_calls', 0)}",
        "",
        "## Cost breakdown",
        "",
        "| Agent | Tokens | Cost USD | Iters |",
        "|-------|--------|----------|-------|",
    ]
    for c in trace.costs:
        lines.append(
            f"| {c.agent} | {c.tokens} | {c.cost_usd:.6f} | {c.iterations} |"
        )
    if not trace.costs:
        lines.append("| — | 0 | 0 | 0 |")
    lines += ["", "## Latency", "", "| Phase | ms | count |", "|-------|-----|-------|"]
    for r in trace.latency:
        lines.append(f"| {r.phase} | {r.duration_ms:.1f} | {r.count} |")
    if not trace.latency:
        lines.append("| — | 0 | 0 |")
    lines += ["", "## Tools", "", "| Step | Tool | Agent | ms | Error | Summary |"]
    lines.append("|------|------|-------|----|-------|---------|")
    for t in trace.tools[:50]:
        lines.append(
            f"| {t.step} | {t.tool} | {t.agent} | {t.duration_ms:.1f} | "
            f"{t.error} | {t.summary[:40]} |"
        )
    if not trace.tools:
        lines.append("| — | — | — | 0 | — | — |")
    lines += ["", "## Reasoning", ""]
    for line in trace.reasoning[-80:]:
        lines.append(f"- {line}")
    if not trace.reasoning:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)
