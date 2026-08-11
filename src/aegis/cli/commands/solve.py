"""`aegis solve` — autonomous local / GitHub issue solving workflow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console

from aegis.bus.pubsub import EventBus
from aegis.config.loader import load_config
from aegis.orchestration.models import WorkflowState
from aegis.orchestration.workflow import run_solve_workflow
from aegis.providers.factory import create_provider, provider_configured, resolve_api_key

console = Console()


def solve_command(
    issue: str = typer.Argument(
        ...,
        help=(
            "Issue text, path to a markdown/text file, or GitHub issue URL "
            "(https://github.com/owner/repo/issues/N or owner/repo#N)"
        ),
    ),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Classify/plan/retrieve only; skip code edits",
    ),
    max_retries: int = typer.Option(3, "--max-retries", min=0, max=10),
    model: str | None = typer.Option(None, "--model", "-m"),
    provider: str | None = typer.Option(None, "--provider", "-p"),
    no_worktree: bool = typer.Option(
        False,
        "--no-worktree",
        help="Edit the workspace in place (skip git worktree isolation)",
    ),
    docker: bool = typer.Option(
        False,
        "--docker",
        help="Run analyze/test pipeline in Docker when the daemon is available",
    ),
    create_pr: bool = typer.Option(
        False,
        "--create-pr",
        help="After a successful solve, push branch and open a GitHub PR (needs token)",
    ),
    pr_base: str = typer.Option("main", "--pr-base", help="Base branch for --create-pr"),
    keep_worktree: bool = typer.Option(
        False,
        "--keep-worktree",
        help="Do not delete the solve worktree after the run (implied by --create-pr)",
    ),
    github_token: str | None = typer.Option(
        None,
        "--github-token",
        help="GitHub token (else GITHUB_TOKEN / GH_TOKEN env)",
        envvar="GITHUB_TOKEN",
    ),
    skip_reviews: bool = typer.Option(
        False,
        "--skip-reviews",
        help="Skip security/perf/regression/dependency review stages",
    ),
    no_memory: bool = typer.Option(
        False,
        "--no-memory",
        help="Disable memory read/write for this run",
    ),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Solve a local or GitHub issue (plan → code → test → reviews → PR draft)."""
    from aegis.github.issues import fetch_issue, looks_like_issue_ref, parse_issue_ref

    issue_text = issue
    issue_url: str | None = None
    issue_ref = None

    issue_path = Path(issue)
    if issue_path.is_file():
        issue_text = issue_path.read_text(encoding="utf-8", errors="replace")
    elif looks_like_issue_ref(issue):
        try:
            issue_ref, _raw, issue_text = fetch_issue(issue, token=github_token)
            issue_url = issue_ref.url
            console.print(f"[dim]Fetched GitHub issue[/dim] {issue_ref.slug}")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Failed to fetch issue:[/red] {exc}")
            raise typer.Exit(1) from exc

    config = load_config()
    provider_name = provider or config.provider.default
    model_name = model or config.provider.model
    use_worktree = (not no_worktree) and config.execution.use_worktree
    use_docker = docker or config.execution.prefer_docker
    keep = keep_worktree or create_pr

    ok, detail = provider_configured(config)
    if not ok and provider_name.lower() not in {"mock", "ollama"}:
        key = resolve_api_key(provider_name, config.provider)
        if not key:
            console.print(f"[red]No API key for provider '{provider_name}'.[/red] ({detail})")
            raise typer.Exit(1)

    bus = EventBus()
    bus.enable_history(True)

    def on_event(event_type: str, data: dict) -> None:
        if event_type in {"agent.start", "agent.done", "agent.error"}:
            console.print(
                f"[dim]{event_type}[/dim] {data.get('agent', data.get('workflow', ''))}"
            )

    bus.subscribe("*", on_event)

    llm = create_provider(config, provider_name=provider_name)
    console.print(
        f"[bold]Aegis solve[/bold]  workspace={workspace}  dry_run={dry_run}  "
        f"worktree={use_worktree and not dry_run}  docker={use_docker}"
    )

    try:
        result = asyncio.run(
            run_solve_workflow(
                issue_text=issue_text,
                workspace=workspace,
                provider=llm,
                model=model_name,
                dry_run=dry_run,
                max_retries=max_retries,
                bus=bus,
                use_worktree=use_worktree,
                use_snapshot=config.execution.snapshot,
                use_docker=use_docker,
                sandbox_image=config.execution.sandbox_image,
                issue_url=issue_url,
                keep_worktree=keep,
                skip_reviews=skip_reviews,
                memory_enabled=(not no_memory) and config.memory.enabled,
                meta={
                    "memory_store_dir": config.memory.store_dir,
                    "memory_global": config.memory.global_memory_enabled,
                },
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130) from None

    # Optional PR creation (explicit flag only — never automatic push)
    if create_pr and result.success and not dry_run:
        try:
            pr_url = _maybe_create_pr(
                result_workspace=Path(result.context.workspace),
                original_workspace=workspace,
                branch=result.context.worktree_branch,
                issue_text=issue_text,
                issue_url=issue_url,
                issue_ref=issue_ref or parse_issue_ref(issue),
                classification=(
                    result.context.classification.summary
                    if result.context.classification
                    else ""
                ),
                plan_summary=(
                    result.context.plan.summary if result.context.plan else ""
                ),
                report_path=result.report_path,
                pr_base=pr_base,
                token=github_token,
            )
            if pr_url:
                result.context.pr_url = pr_url
                console.print(f"[green]PR opened:[/green] {pr_url}")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]PR creation skipped/failed:[/yellow] {exc}")

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "state": result.state.value,
                    "success": result.success,
                    "error": result.context.error,
                    "retries": result.context.retries,
                    "classification": (
                        result.context.classification.model_dump()
                        if result.context.classification
                        else None
                    ),
                    "plan_summary": (
                        result.context.plan.summary if result.context.plan else None
                    ),
                    "analysis_passed": (
                        result.context.analysis.passed if result.context.analysis else None
                    ),
                    "tests_passed": (
                        result.context.tests.passed if result.context.tests else None
                    ),
                    "changed_files": result.context.changed_files,
                    "worktree_branch": result.context.worktree_branch,
                    "issue_url": result.context.issue_url,
                    "pr_url": result.context.pr_url,
                    "pr_draft": (
                        result.context.pr_draft.model_dump()
                        if result.context.pr_draft
                        else None
                    ),
                    "reviews": (
                        result.context.reviews.model_dump()
                        if result.context.reviews
                        else None
                    ),
                    "memory_hits": result.context.memory_hits,
                    "report_path": result.report_path,
                    "trace_id": result.context.meta.get("trace_id"),
                    "trace_path": result.context.meta.get("trace_path"),
                },
                indent=2,
            )
        )
    else:
        if result.success:
            console.print(f"[bold green]COMPLETE[/bold green] state={result.state.value}")
        else:
            console.print(
                f"[bold red]{result.state.value.upper()}[/bold red] "
                f"{result.context.error or ''}"
            )
        if result.context.classification:
            c = result.context.classification
            console.print(f"  type={c.type} complexity={c.complexity} — {c.summary}")
        if result.context.plan:
            console.print(
                f"  plan: {result.context.plan.summary or '(steps)'} "
                f"[{len(result.context.plan.steps)} steps]"
            )
        if result.context.analysis:
            console.print(
                f"  analyze: {'pass' if result.context.analysis.passed else 'fail'}"
            )
        if result.context.tests:
            console.print(f"  tests: {'pass' if result.context.tests.passed else 'fail'}")
        if result.context.reviews:
            r = result.context.reviews
            sec = "pass" if r.security and r.security.passed else "n/a"
            console.print(
                f"  reviews: security={sec} "
                f"regression={r.regression.regression_risk if r.regression else 'n/a'} "
                f"blocking={r.blocking}"
            )
        if result.context.pr_draft:
            console.print(f"  pr draft: {result.context.pr_draft.pr_title[:60]}")
        if result.context.changed_files:
            console.print(f"  changed: {', '.join(result.context.changed_files[:8])}")
        if result.context.worktree_branch:
            console.print(f"  branch: {result.context.worktree_branch}")
        if result.context.pr_url:
            console.print(f"  pr: {result.context.pr_url}")
        if result.report_path:
            console.print(f"[dim]Report: {result.report_path}[/dim]")
        trace_id = result.context.meta.get("trace_id")
        if trace_id:
            console.print(
                f"[dim]Trace: {trace_id}  "
                f"(aegis observe show {trace_id})[/dim]"
            )

    if result.state is WorkflowState.COMPLETE:
        raise typer.Exit(0)
    raise typer.Exit(1)


def _maybe_create_pr(
    *,
    result_workspace: Path,
    original_workspace: Path,
    branch: str | None,
    issue_text: str,
    issue_url: str | None,
    issue_ref: object | None,
    classification: str,
    plan_summary: str,
    report_path: str | None,
    pr_base: str,
    token: str | None,
) -> str | None:
    from aegis.github.client import GitHubClient, GitHubError
    from aegis.github.issues import ParsedIssueRef
    from aegis.github.pr import (
        build_pr_body,
        create_pull_request,
        detect_github_remote,
        push_branch,
    )
    from aegis.worktree.worktree import WorktreeSession

    if not branch:
        raise GitHubError(
            "No worktree branch available — re-run without --no-worktree "
            "and with --create-pr / --keep-worktree"
        )

    # Commit in the worktree if it still exists
    work_path = result_workspace if result_workspace.is_dir() else original_workspace
    if not work_path.is_dir():
        raise GitHubError(f"Worktree path missing: {work_path}")

    # Lightweight session for commit helpers
    session = WorktreeSession(
        repo=original_workspace,
        path=work_path,
        branch=branch,
        base_ref="HEAD",
        created=False,
    )
    title = plan_summary or classification or f"Aegis fix ({branch})"
    title = title.strip().splitlines()[0][:72]
    sha = session.commit(f"fix: {title}\n\nMade-with: Aegis Engineer")
    if not sha:
        # still allow PR if commits already exist
        pass

    push_branch(work_path, branch)

    remote = detect_github_remote(original_workspace)
    owner = repo = None
    if isinstance(issue_ref, ParsedIssueRef):
        owner, repo = issue_ref.owner, issue_ref.repo
    elif remote:
        owner, repo = remote
    if not owner or not repo:
        raise GitHubError("Could not determine GitHub owner/repo for PR")

    body = build_pr_body(
        issue_text=issue_text,
        classification_summary=classification,
        plan_summary=plan_summary,
        report_path=report_path,
        issue_url=issue_url,
    )
    client = GitHubClient(token=token)
    pr = create_pull_request(
        owner,
        repo,
        title=title,
        body=body,
        head=branch,
        base=pr_base,
        client=client,
    )
    return pr.url or None
