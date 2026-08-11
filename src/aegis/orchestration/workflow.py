"""Solve workflow state machine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.orchestration.models import WorkflowContext, WorkflowResult, WorkflowState
from aegis.orchestration.stages import (
    persist_run_memory,
    stage_analyze,
    stage_classify,
    stage_code,
    stage_plan,
    stage_pr_draft,
    stage_retrieve,
    stage_reviews,
    stage_test,
)
from aegis.providers.base import LLMProvider


async def run_solve_workflow(
    *,
    issue_text: str,
    workspace: Path,
    provider: LLMProvider,
    model: str,
    dry_run: bool = False,
    max_retries: int = 3,
    bus: EventBus | None = None,
    use_worktree: bool | None = None,
    use_snapshot: bool = True,
    use_docker: bool = False,
    sandbox_image: str = "python:3.12-slim",
    issue_url: str | None = None,
    keep_worktree: bool = False,
    meta: dict[str, Any] | None = None,
    skip_reviews: bool = False,
    memory_enabled: bool = True,
) -> WorkflowResult:
    """Run CLASSIFY → PLAN → RETRIEVE → CODE ⇄ ANALYZE/TEST → REVIEW → PR.

    Phase 9: worktree/snapshot/docker. Phase 10: memory + parallel reviews + PR draft.
    """
    bus = bus or EventBus()
    original_workspace = Path(workspace).resolve()
    work_root = original_workspace
    worktree_session = None
    snapshot = None

    # Observability collector (Phase 11)
    collector = None
    try:
        from aegis.observability.collector import TraceCollector

        collector = TraceCollector(
            workspace=str(original_workspace),
            workflow="solve",
        )
        collector.attach(bus)
    except Exception:  # noqa: BLE001
        collector = None

    # --- isolation: worktree (git) ---
    if use_worktree is None:
        use_worktree = True
    if use_worktree and not dry_run:
        try:
            from aegis.worktree.worktree import create_worktree, is_git_repo

            if is_git_repo(original_workspace):
                worktree_session = create_worktree(original_workspace)
                work_root = worktree_session.path
        except Exception:  # noqa: BLE001 — isolation is best-effort
            worktree_session = None
            work_root = original_workspace

    # --- isolation: snapshot ---
    if use_snapshot and not dry_run:
        try:
            from aegis.snapshot.snapshot import SnapshotSession

            snapshot = SnapshotSession.capture(work_root)
        except OSError:
            snapshot = None

    ctx = WorkflowContext(
        issue_text=issue_text,
        workspace=str(work_root),
        dry_run=dry_run,
        max_retries=max_retries,
        issue_url=issue_url,
        worktree_path=str(worktree_session.path) if worktree_session else None,
        worktree_branch=worktree_session.branch if worktree_session else None,
        meta={
            "use_docker": use_docker,
            "sandbox_image": sandbox_image,
            "original_workspace": str(original_workspace),
            "memory_enabled": memory_enabled,
            **(meta or {}),
        },
    )
    ctx.state = WorkflowState.IDLE
    ctx.log(
        "start",
        dry_run=dry_run,
        worktree=bool(worktree_session),
        snapshot=bool(snapshot),
        use_docker=use_docker,
    )
    await bus.publish(
        EventType.AGENT_START,
        {
            "agent": "manager",
            "workflow": "solve",
            "workspace": ctx.workspace,
            "worktree": ctx.worktree_branch,
        },
    )

    try:
        # CLASSIFY
        ctx.state = WorkflowState.CLASSIFY
        ctx.log("enter")
        if collector:
            collector.mark_phase("classify", enter=True)
        ctx.classification = await stage_classify(ctx, provider, model, bus)
        if collector:
            collector.mark_phase("classify", enter=False)
        ctx.log("classification", data=ctx.classification.model_dump())

        # PLAN
        ctx.state = WorkflowState.PLAN
        ctx.log("enter")
        if collector:
            collector.mark_phase("plan", enter=True)
        ctx.plan = await stage_plan(ctx, provider, model, bus)
        if collector:
            collector.mark_phase("plan", enter=False)
        ctx.log("plan", steps=len(ctx.plan.steps), summary=ctx.plan.summary)

        # RETRIEVE
        ctx.state = WorkflowState.RETRIEVE
        ctx.log("enter")
        if collector:
            collector.mark_phase("retrieve", enter=True)
        ctx.context = await stage_retrieve(ctx, provider, model, bus)
        if collector:
            collector.mark_phase("retrieve", enter=False)
        ctx.log("retrieve", snippets=len(ctx.context.snippets))

        # CODE loop with analyze/test
        while True:
            ctx.state = WorkflowState.CODE
            ctx.log("enter", retry=ctx.retries)
            if collector:
                collector.mark_phase("code", enter=True)
            code_result = await stage_code(ctx, provider, model, bus)
            if collector:
                collector.mark_phase("code", enter=False)
                if code_result.total_tokens or code_result.cost_usd:
                    collector.record_agent_usage(
                        "coder",
                        tokens=code_result.total_tokens,
                        cost_usd=code_result.cost_usd,
                        iterations=code_result.iterations,
                    )
            ctx.code_summary = (code_result.output or "")[:4000]
            ctx.log(
                "code_done",
                error=code_result.error,
                iterations=code_result.iterations,
                tool_calls=code_result.tool_calls,
            )
            if code_result.error and code_result.error != "max_iterations_exceeded":
                pass

            ctx.state = WorkflowState.ANALYZE
            ctx.log("enter")
            if collector:
                collector.mark_phase("analyze", enter=True)
            ctx.analysis = stage_analyze(ctx)
            if collector:
                collector.mark_phase("analyze", enter=False)
            ctx.log("analyze", passed=ctx.analysis.passed, errors=len(ctx.analysis.errors))
            if not ctx.analysis.passed:
                ctx.retries += 1
                if ctx.retries >= ctx.max_retries:
                    ctx.state = WorkflowState.FAILED
                    ctx.error = "Static analysis failed after max retries"
                    ctx.log("failed", reason=ctx.error)
                    break
                ctx.log("retry", reason="analyze_failed", retries=ctx.retries)
                continue

            ctx.state = WorkflowState.TEST
            ctx.log("enter")
            if collector:
                collector.mark_phase("test", enter=True)
            ctx.tests = stage_test(ctx)
            if collector:
                collector.mark_phase("test", enter=False)
            ctx.log(
                "test",
                passed=ctx.tests.passed,
                failed=ctx.tests.failed,
                total=ctx.tests.total,
            )
            if not ctx.tests.passed:
                ctx.retries += 1
                if ctx.retries >= ctx.max_retries:
                    ctx.state = WorkflowState.FAILED
                    ctx.error = "Tests failed after max retries"
                    ctx.log("failed", reason=ctx.error)
                    break
                ctx.log("retry", reason="tests_failed", retries=ctx.retries)
                continue

            # Capture changed files before reviews (reviews read them)
            if snapshot is not None:
                try:
                    ctx.changed_files = snapshot.changed_files()
                    ctx.meta["diff"] = snapshot.diff_summary()
                except OSError:
                    pass
            elif worktree_session is not None:
                try:
                    ctx.changed_files = worktree_session.changed_files()
                except Exception:  # noqa: BLE001
                    pass

            # REVIEW (security ∥ perf, then regression ∥ dependency)
            if not skip_reviews:
                ctx.state = WorkflowState.REVIEW
                ctx.log("enter")
                if collector:
                    collector.mark_phase("review", enter=True)
                ctx.reviews = await stage_reviews(ctx, provider, model, bus)
                if collector:
                    collector.mark_phase("review", enter=False)
                ctx.log(
                    "reviews",
                    blocking=ctx.reviews.blocking,
                    security_passed=(
                        ctx.reviews.security.passed if ctx.reviews.security else None
                    ),
                    perf_passed=(
                        ctx.reviews.performance.passed if ctx.reviews.performance else None
                    ),
                    regression_risk=(
                        ctx.reviews.regression.regression_risk
                        if ctx.reviews.regression
                        else None
                    ),
                )
                if ctx.reviews.blocking and not dry_run:
                    ctx.retries += 1
                    if ctx.retries >= ctx.max_retries:
                        ctx.state = WorkflowState.FAILED
                        ctx.error = "Reviews blocked merge after max retries"
                        ctx.log("failed", reason=ctx.error)
                        break
                    ctx.log("retry", reason="reviews_blocked", retries=ctx.retries)
                    continue

            # PR draft
            ctx.state = WorkflowState.PR
            ctx.log("enter")
            if collector:
                collector.mark_phase("pr", enter=True)
            ctx.pr_draft = await stage_pr_draft(ctx, provider, model, bus)
            if collector:
                collector.mark_phase("pr", enter=False)
            ctx.log(
                "pr_draft",
                title=ctx.pr_draft.pr_title[:80] if ctx.pr_draft else None,
            )

            ctx.state = WorkflowState.COMPLETE
            ctx.log("complete")
            break

    except Exception as exc:  # noqa: BLE001
        ctx.state = WorkflowState.FAILED
        ctx.error = str(exc)
        ctx.log("exception", error=str(exc))

    # Ensure changed files tracked even on failure
    if not ctx.changed_files:
        if snapshot is not None:
            try:
                ctx.changed_files = snapshot.changed_files()
                ctx.meta["diff"] = snapshot.diff_summary()
            except OSError:
                pass
        elif worktree_session is not None:
            try:
                ctx.changed_files = worktree_session.changed_files()
            except Exception:  # noqa: BLE001
                pass

    success = ctx.state is WorkflowState.COMPLETE

    # Memory: learn from success or failure (skip pure dry-run success noise optional)
    if memory_enabled and (success or ctx.error):
        if not (dry_run and success):
            mem_id = persist_run_memory(ctx, success=success)
            if mem_id:
                ctx.meta["memory_entry_id"] = mem_id
                ctx.log("memory_written", id=mem_id, success=success)

    # When using a worktree: on success, copy changed files back into the
    # original workspace so the fix is not lost when the worktree is removed.
    # On failure, discard (main tree stays clean). With keep_worktree, leave
    # files only in the worktree (e.g. pending --create-pr).
    if worktree_session is not None and success and not keep_worktree:
        try:
            applied = _apply_worktree_changes(
                worktree_session.path,
                original_workspace,
                ctx.changed_files,
            )
            ctx.meta["applied_to_workspace"] = applied
            ctx.log("applied_worktree_changes", files=applied)
        except OSError as exc:
            ctx.log("apply_worktree_error", error=str(exc))

    # Snapshot-only failure: leave reverts to the caller / explicit API.

    ctx.finished_at = datetime.now(UTC)
    report_workspace = original_workspace
    report_path = _write_report(ctx, report_root=report_workspace)

    # Cleanup worktree unless kept for PR / inspection
    if worktree_session is not None and not keep_worktree:
        try:
            worktree_session.cleanup()
            ctx.log("worktree_cleaned")
        except Exception as exc:  # noqa: BLE001
            ctx.log("worktree_cleanup_error", error=str(exc))

    await bus.publish(
        EventType.AGENT_DONE if success else EventType.AGENT_ERROR,
        {
            "agent": "manager",
            "workflow": "solve",
            "state": ctx.state.value,
            "success": success,
            "error": ctx.error,
            "changed_files": ctx.changed_files,
        },
    )

    # Persist observability trace
    if collector is not None:
        try:
            collector.finish(
                success=success,
                meta={
                    "state": ctx.state.value,
                    "error": ctx.error,
                    "report_path": str(report_path) if report_path else None,
                    "changed_files": ctx.changed_files,
                },
            )
            trace_path = collector.save(original_workspace)
            ctx.meta["trace_id"] = collector.trace.id
            ctx.meta["trace_path"] = str(trace_path)
            collector.detach()
        except Exception:  # noqa: BLE001
            try:
                collector.detach()
            except Exception:  # noqa: BLE001
                pass

    return WorkflowResult(
        state=ctx.state,
        context=ctx,
        success=success,
        report_path=str(report_path) if report_path else None,
    )


def _apply_worktree_changes(
    worktree_path: Path,
    dest_root: Path,
    changed_files: list[str],
) -> list[str]:
    """Copy changed files from worktree into the original workspace."""
    import shutil

    applied: list[str] = []
    for rel in changed_files:
        src = worktree_path / rel
        dst = dest_root / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            applied.append(rel)
        elif not src.exists() and dst.is_file():
            dst.unlink()
            applied.append(rel)
    return applied


def _write_report(
    ctx: WorkflowContext, *, report_root: Path | None = None
) -> Path | None:
    try:
        root = report_root or Path(ctx.workspace)
        out_dir = root / ".aegis" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"solve-{stamp}.md"
        lines = [
            "# Aegis Solve Report",
            "",
            f"**Workspace:** `{ctx.workspace}`  ",
            f"**State:** `{ctx.state.value}`  ",
            f"**Dry run:** {ctx.dry_run}  ",
            f"**Retries:** {ctx.retries}/{ctx.max_retries}  ",
            f"**Started:** {ctx.started_at.isoformat()}  ",
            f"**Finished:** {ctx.finished_at.isoformat() if ctx.finished_at else '—'}  ",
            "",
        ]
        if ctx.issue_url:
            lines += [f"**Issue URL:** {ctx.issue_url}  ", ""]
        if ctx.worktree_branch:
            lines += [
                f"**Worktree branch:** `{ctx.worktree_branch}`  ",
                f"**Worktree path:** `{ctx.worktree_path}`  ",
                "",
            ]
        lines += [
            "## Issue",
            "",
            "```",
            ctx.issue_text[:5000],
            "```",
            "",
        ]
        if ctx.classification:
            lines += [
                "## Classification",
                "",
                f"- **type:** {ctx.classification.type}",
                f"- **complexity:** {ctx.classification.complexity}",
                f"- **summary:** {ctx.classification.summary}",
                f"- **files:** {', '.join(ctx.classification.estimated_files) or '—'}",
                "",
            ]
        if ctx.plan:
            lines += ["## Plan", "", f"{ctx.plan.summary}", ""]
            for s in ctx.plan.steps:
                lines.append(f"{s.step}. {s.description} (`{', '.join(s.files)}`)")
            lines.append("")
        if ctx.code_summary:
            lines += ["## Code summary", "", ctx.code_summary[:3000], ""]
        if ctx.changed_files:
            lines += ["## Changed files", ""]
            for f in ctx.changed_files:
                lines.append(f"- `{f}`")
            lines.append("")
        if ctx.analysis:
            lines += [
                "## Static analysis",
                "",
                f"**passed:** {ctx.analysis.passed}",
                f"**command:** `{ctx.analysis.command}`",
                "",
                "```",
                ctx.analysis.output_tail[:2000],
                "```",
                "",
            ]
        if ctx.tests:
            lines += [
                "## Tests",
                "",
                f"**passed:** {ctx.tests.passed}",
                f"**command:** `{ctx.tests.command}`",
                f"**total/failed:** {ctx.tests.total}/{ctx.tests.failed}",
                "",
                "```",
                ctx.tests.output_tail[:2000],
                "```",
                "",
            ]
        if ctx.reviews:
            lines += ["## Reviews", ""]
            if ctx.reviews.security:
                lines.append(
                    f"- **security:** "
                    f"{'pass' if ctx.reviews.security.passed else 'FAIL'} "
                    f"({len(ctx.reviews.security.vulnerabilities)} findings)"
                )
            if ctx.reviews.performance:
                lines.append(
                    f"- **performance:** "
                    f"{'pass' if ctx.reviews.performance.passed else 'FAIL'} "
                    f"({len(ctx.reviews.performance.issues)} findings)"
                )
            if ctx.reviews.regression:
                lines.append(
                    f"- **regression risk:** {ctx.reviews.regression.regression_risk}"
                )
            if ctx.reviews.dependency:
                lines.append(
                    f"- **dependency:** {ctx.reviews.dependency.summary or '—'} "
                    f"(risk={ctx.reviews.dependency.risk_level})"
                )
            lines.append("")
        if ctx.pr_draft:
            lines += [
                "## PR draft",
                "",
                f"**title:** {ctx.pr_draft.pr_title}",
                "",
                "```",
                ctx.pr_draft.pr_body[:3000],
                "```",
                "",
            ]
        if ctx.memory_hits:
            lines += ["## Memory hits", ""]
            for h in ctx.memory_hits[:8]:
                lines.append(
                    f"- [{h.get('kind')}] {h.get('title')} (score={h.get('score')})"
                )
            lines.append("")
        if ctx.pr_url:
            lines += ["## Pull request", "", ctx.pr_url, ""]
        if ctx.error:
            lines += ["## Error", "", ctx.error, ""]
        lines += ["## History", ""]
        for h in ctx.history:
            extra = {k: v for k, v in h.items() if k not in ("ts", "state", "event")}
            lines.append(
                f"- `{h.get('ts')}` **{h.get('state')}** {h.get('event')} {extra}"
            )
        path.write_text("\n".join(lines), encoding="utf-8")
        (out_dir / "solve-latest.md").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (out_dir / "solve-latest.json").write_text(
            json.dumps(
                {
                    "state": ctx.state.value,
                    "success": ctx.state is WorkflowState.COMPLETE,
                    "retries": ctx.retries,
                    "error": ctx.error,
                    "dry_run": ctx.dry_run,
                    "report": str(path),
                    "issue_url": ctx.issue_url,
                    "worktree_branch": ctx.worktree_branch,
                    "changed_files": ctx.changed_files,
                    "pr_url": ctx.pr_url,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path
    except OSError:
        return None
