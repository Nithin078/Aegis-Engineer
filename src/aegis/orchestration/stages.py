"""Stage implementations for the solve workflow."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aegis.agents.base import AgentResult
from aegis.agents.loop import agent_loop
from aegis.agents.specialists import (
    make_classifier,
    make_coder,
    make_dependency_analyzer,
    make_doc_retriever,
    make_perf_reviewer,
    make_planner,
    make_pr_generator,
    make_regression_detector,
    make_retriever,
    make_security_reviewer,
)
from aegis.bus.pubsub import EventBus
from aegis.config.schema import PermissionsConfig
from aegis.orchestration.models import (
    AnalysisResult,
    ContextBundle,
    DependencyReview,
    ImplementationPlan,
    IssueClassification,
    PerfReview,
    PlanStep,
    PRDraft,
    RegressionReview,
    ReviewBundle,
    SecurityReview,
    TestResult,
    WorkflowContext,
)
from aegis.permissions.engine import PermissionEngine
from aegis.providers.base import LLMProvider
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _registry(bus: EventBus, trust: str = "yolo") -> Any:
    eng = PermissionEngine(
        PermissionsConfig(default="allow", trust_mode=trust, rules=[])  # type: ignore[arg-type]
    )
    return create_default_registry(permission_engine=eng, event_bus=bus)


async def stage_classify(
    ctx: WorkflowContext,
    provider: LLMProvider,
    model: str,
    bus: EventBus,
) -> IssueClassification:
    """LLM classify with heuristic fallback."""
    root = Path(ctx.workspace)
    agent = make_classifier()
    tools = _registry(bus)
    tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=30)
    task = f"Repository: {root}\n\nIssue:\n{ctx.issue_text}"
    result = await agent_loop(agent, task, provider, tools, tctx, model=model, event_bus=bus)
    data = _extract_json(result.output or "")
    if data:
        return IssueClassification.model_validate(
            {
                "type": data.get("type", "bug"),
                "complexity": data.get("complexity", "moderate"),
                "summary": data.get("summary", "")[:500],
                "subsystems": data.get("subsystems") or [],
                "estimated_files": data.get("estimated_files") or [],
            }
        )
    return _heuristic_classify(ctx.issue_text, root)


def _heuristic_classify(issue: str, root: Path) -> IssueClassification:
    low = issue.lower()
    typ = "bug"
    if any(w in low for w in ("feature", "add ", "implement", "support")):
        typ = "feature"
    elif any(w in low for w in ("refactor", "cleanup", "rename")):
        typ = "refactor"
    elif any(w in low for w in ("doc", "readme")):
        typ = "docs"
    files: list[str] = []
    for m in re.finditer(r"[\w./\\-]+\.py\b", issue):
        files.append(m.group(0).replace("\\", "/"))
    return IssueClassification(
        type=typ,
        complexity="trivial" if len(issue) < 80 else "moderate",
        summary=issue.strip().splitlines()[0][:200] if issue.strip() else "issue",
        estimated_files=files[:10],
    )


def _memory_context(ctx: WorkflowContext) -> tuple[str, list[dict[str, Any]]]:
    """Query memory for planning hints; returns (prompt block, hit dicts)."""
    if ctx.meta.get("memory_enabled") is False:
        return "", []
    try:
        from aegis.memory.models import MemoryKind
        from aegis.memory.store import MemoryStore

        store = MemoryStore(
            ctx.workspace,
            store_dir=str(ctx.meta.get("memory_store_dir") or ".aegis/memory"),
            global_enabled=bool(ctx.meta.get("memory_global", True)),
        )
        result = store.query(
            ctx.issue_text,
            limit=5,
            kinds=[MemoryKind.SOLVED, MemoryKind.FAILURE, MemoryKind.PATTERN, MemoryKind.GLOBAL],
        )
        hits = [
            {
                "id": e.id,
                "kind": e.kind.value,
                "title": e.title,
                "summary": e.summary,
                "score": e.score,
            }
            for e in result.entries
        ]
        ctx.memory_hits = hits
        return store.format_for_prompt(result), hits
    except Exception as exc:  # noqa: BLE001
        return f"(memory unavailable: {exc})", []


async def stage_plan(
    ctx: WorkflowContext,
    provider: LLMProvider,
    model: str,
    bus: EventBus,
) -> ImplementationPlan:
    root = Path(ctx.workspace)
    agent = make_planner()
    tools = _registry(bus)
    tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=30)
    clf = ctx.classification.model_dump() if ctx.classification else {}
    mem_block, hits = _memory_context(ctx)
    task = (
        f"Workspace: {root}\nClassification: {json.dumps(clf)}\n\n"
        f"Memory hints:\n{mem_block or '(none)'}\n\n"
        f"Issue:\n{ctx.issue_text}\n\nProduce the JSON plan."
    )
    result = await agent_loop(agent, task, provider, tools, tctx, model=model, event_bus=bus)
    data = _extract_json(result.output or "")
    memory_hints = [f"{h['kind']}: {h['title']}" for h in hits[:5]]
    if data and data.get("steps"):
        steps = []
        for i, s in enumerate(data.get("steps") or [], start=1):
            if not isinstance(s, dict):
                continue
            steps.append(
                PlanStep(
                    step=int(s.get("step") or i),
                    description=str(s.get("description") or ""),
                    files=list(s.get("files") or []),
                    expected_output=str(s.get("expected_output") or ""),
                )
            )
        return ImplementationPlan(
            steps=steps,
            risk_level=str(data.get("risk_level") or "medium"),
            summary=str(data.get("summary") or ""),
            memory_hints=memory_hints,
        )
    plan = _heuristic_plan(ctx)
    plan.memory_hints = memory_hints
    return plan


def _heuristic_plan(ctx: WorkflowContext) -> ImplementationPlan:
    files = list(ctx.classification.estimated_files) if ctx.classification else []
    steps = [
        PlanStep(step=1, description="Inspect relevant source and tests", files=files),
        PlanStep(step=2, description="Implement the fix with minimal edits", files=files),
        PlanStep(step=3, description="Ensure tests pass", files=files),
    ]
    if ctx.memory_hits:
        steps.insert(
            0,
            PlanStep(
                step=0,
                description=f"Consider past memory: {ctx.memory_hits[0].get('title', '')}",
                files=files,
            ),
        )
    return ImplementationPlan(
        steps=steps,
        risk_level="medium",
        summary=ctx.classification.summary if ctx.classification else "Implement issue",
    )


async def stage_retrieve(
    ctx: WorkflowContext,
    provider: LLMProvider,
    model: str,
    bus: EventBus,
) -> ContextBundle:
    root = Path(ctx.workspace)
    # Always attach intelligence if available
    intel: dict[str, Any] = {}
    try:
        from aegis.intelligence.engine import IntelligenceEngine

        eng = IntelligenceEngine(root)
        if not eng.index:
            eng.build()
        if ctx.classification and ctx.classification.estimated_files:
            f0 = ctx.classification.estimated_files[0]
            intel["impact"] = eng.impact(f0)
        intel["search"] = eng.hybrid_search(ctx.issue_text[:200], limit=10)
    except Exception as exc:  # noqa: BLE001
        intel["error"] = str(exc)

    agent = make_retriever()
    tools = _registry(bus)
    tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=30)
    plan = ctx.plan.model_dump() if ctx.plan else {}
    task = (
        f"Workspace: {root}\nPlan: {json.dumps(plan)[:2000]}\n\n"
        f"Issue:\n{ctx.issue_text}\n\nReturn JSON context snippets."
    )
    result = await agent_loop(agent, task, provider, tools, tctx, model=model, event_bus=bus)
    data = _extract_json(result.output or "") or {}
    snippets = data.get("snippets") if isinstance(data.get("snippets"), list) else []

    # Documentation retrieval: deterministic scan first (no extra LLM turn).
    # Optional LLM pass when meta.llm_docs is true.
    docs, doc_notes = _collect_docs(root, ctx.issue_text)
    if ctx.meta.get("llm_docs"):
        try:
            doc_agent = make_doc_retriever()
            dtctx = ToolContext(
                workspace_root=root, agent=doc_agent.name, event_bus=bus, timeout=30
            )
            dtask = (
                f"Workspace: {root}\nIssue:\n{ctx.issue_text}\n\n"
                "Find README/docs relevant to this change. JSON only."
            )
            dresult = await agent_loop(
                doc_agent, dtask, provider, tools, dtctx, model=model, event_bus=bus
            )
            ddata = _extract_json(dresult.output or "") or {}
            raw_docs = ddata.get("docs") if isinstance(ddata.get("docs"), list) else []
            for d in raw_docs:
                if isinstance(d, dict):
                    docs.append(d)
            docs = docs[:20]
            if ddata.get("notes"):
                doc_notes = str(ddata.get("notes"))[:1000]
        except Exception as exc:  # noqa: BLE001
            doc_notes = f"{doc_notes}; llm docs error: {exc}"[:1000]

    notes = str(data.get("notes") or result.output or "")[:2000]
    if doc_notes:
        notes = f"{notes}\n\nDocs: {doc_notes}"[:2000]
    return ContextBundle(
        snippets=[s for s in snippets if isinstance(s, dict)][:30],
        intelligence=intel,
        docs=docs,
        notes=notes,
    )


def _collect_docs(root: Path, issue: str) -> tuple[list[dict[str, Any]], str]:
    """Scan common doc locations without an LLM call."""
    docs: list[dict[str, Any]] = []
    candidates: list[Path] = []
    for name in ("README.md", "README.rst", "CONTRIBUTING.md", "ARCHITECTURE.md"):
        p = root / name
        if p.is_file():
            candidates.append(p)
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.rglob("*.md"))[:15]:
            candidates.append(p)
    keywords = {w.lower() for w in re.findall(r"[a-zA-Z_]{3,}", issue)}
    for path in candidates[:20]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:1500]
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        low = text.lower()
        hit = any(k in low for k in keywords) if keywords else True
        if hit or path.name.upper().startswith("README"):
            docs.append(
                {
                    "path": rel,
                    "excerpt": text[:400],
                    "relevance": "keyword match" if hit else "project readme",
                }
            )
    notes = f"found {len(docs)} doc file(s)" if docs else "no docs found"
    return docs, notes


async def stage_code(
    ctx: WorkflowContext,
    provider: LLMProvider,
    model: str,
    bus: EventBus,
) -> AgentResult:
    root = Path(ctx.workspace)
    if ctx.dry_run:
        return AgentResult(output="dry_run: skipped code changes", iterations=0)

    agent = make_coder()
    tools = _registry(bus)
    tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=60)
    feedback = ""
    if ctx.analysis and not ctx.analysis.passed:
        feedback += f"\nStatic analysis failed:\n{ctx.analysis.output_tail[:1500]}\n"
    if ctx.tests and not ctx.tests.passed:
        feedback += f"\nTests failed:\n{ctx.tests.output_tail[:1500]}\n"

    task = (
        f"Workspace: {root}\n"
        f"Issue:\n{ctx.issue_text}\n\n"
        f"Plan:\n{json.dumps(ctx.plan.model_dump() if ctx.plan else {}, indent=2)[:3000]}\n\n"
        f"Context notes:\n{(ctx.context.notes if ctx.context else '')[:1500]}\n"
        f"{feedback}\n"
        "Implement the fix now using edit/write tools."
    )
    return await agent_loop(agent, task, provider, tools, tctx, model=model, event_bus=bus)


def stage_analyze(ctx: WorkflowContext) -> AnalysisResult:
    """Deterministic static analysis via quality pipeline (ruff check)."""
    root = Path(ctx.workspace)
    if ctx.dry_run:
        return AnalysisResult(passed=True, warnings=["dry_run"], command=None)

    from aegis.execution.pipeline import run_quality_pipeline

    pipe = run_quality_pipeline(
        root,
        timeout=120.0,
        use_docker=bool(ctx.meta.get("use_docker")),
        sandbox_image=str(ctx.meta.get("sandbox_image") or "python:3.12-slim"),
        format_code=False,
        lint=True,
        test=False,
    )
    lint = pipe.step("lint")
    if lint is None:
        return AnalysisResult(passed=True, warnings=["lint step missing"], command=None)
    if lint.skipped:
        return AnalysisResult(
            passed=True,
            warnings=[lint.reason or "lint skipped"],
            command=None,
        )
    assert lint.result is not None
    out = lint.result.output
    errors = [] if lint.result.ok else [ln for ln in out.splitlines() if ln.strip()][:30]
    return AnalysisResult(
        passed=lint.result.ok,
        errors=errors,
        command=lint.result.command_display,
        output_tail=out[-3000:],
    )


def stage_test(ctx: WorkflowContext) -> TestResult:
    """Deterministic pytest via quality pipeline (sys.executable -m)."""
    root = Path(ctx.workspace)
    if ctx.dry_run:
        return TestResult(passed=True, command=None, output_tail="dry_run")

    from aegis.execution.pipeline import run_quality_pipeline

    pipe = run_quality_pipeline(
        root,
        timeout=300.0,
        use_docker=bool(ctx.meta.get("use_docker")),
        sandbox_image=str(ctx.meta.get("sandbox_image") or "python:3.12-slim"),
        format_code=False,
        lint=False,
        test=True,
    )
    test_step = pipe.step("test")
    if test_step is None:
        return TestResult(passed=True, command=None, output_tail="test step missing")
    if test_step.skipped:
        # "no tests" is a soft pass; missing pytest with tests present is fail
        soft = "no tests" in (test_step.reason or "").lower()
        return TestResult(
            passed=soft,
            command=None,
            output_tail=test_step.reason or "skipped",
            failures=[] if soft else [test_step.reason or "skipped"],
        )
    assert test_step.result is not None
    out = test_step.result.output
    failures = []
    if not test_step.result.ok:
        failures = [
            line
            for line in out.splitlines()
            if "FAILED" in line or "ERROR" in line or "AssertionError" in line
        ][:20]
    total = failed = 0
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m2 = re.search(r"(\d+) passed", out)
    if m2:
        total = int(m2.group(1)) + failed
    return TestResult(
        passed=test_step.result.ok,
        total=total,
        failed=failed,
        command=test_step.result.command_display,
        output_tail=out[-4000:],
        failures=failures,
    )


def _changed_file_blobs(ctx: WorkflowContext, *, max_files: int = 12, max_bytes: int = 8000) -> str:
    root = Path(ctx.workspace)
    files = list(ctx.changed_files)[:max_files]
    if not files and ctx.classification:
        files = list(ctx.classification.estimated_files)[:max_files]
    parts: list[str] = []
    for rel in files:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
        except OSError:
            continue
        parts.append(f"### {rel}\n```\n{text}\n```")
    return "\n\n".join(parts)[:40_000]


def _heuristic_security(blobs: str) -> SecurityReview:
    vulns: list[dict[str, Any]] = []
    secret_pat = r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}"
    patterns = [
        (secret_pat, "hardcoded_secret", "high"),
        (r"\beval\s*\(", "unsafe_eval", "high"),
        (r"\bexec\s*\(", "unsafe_exec", "high"),
        (r"pickle\.loads\s*\(", "insecure_deserialization", "medium"),
        (r"shell\s*=\s*True", "shell_injection_risk", "medium"),
    ]
    for pat, typ, sev in patterns:
        if re.search(pat, blobs):
            vulns.append(
                {
                    "file": "?",
                    "line": 0,
                    "type": typ,
                    "severity": sev,
                    "description": f"Heuristic match for {typ}",
                    "fix": "Review and remediate before merge",
                }
            )
    blocking = any(v.get("severity") in {"critical", "high"} for v in vulns)
    return SecurityReview(passed=not blocking, vulnerabilities=vulns)


def _heuristic_perf(blobs: str) -> PerfReview:
    issues: list[dict[str, Any]] = []
    if re.search(r"for .+ in .+:\n(?:.*\n){0,3}.*for .+ in", blobs):
        issues.append(
            {
                "file": "?",
                "line": 0,
                "type": "complexity",
                "severity": "low",
                "description": "Possible nested loop",
                "fix": "Consider algorithmic improvement if on hot path",
            }
        )
    return PerfReview(passed=True, issues=issues)


async def stage_reviews(
    ctx: WorkflowContext,
    provider: LLMProvider,
    model: str,
    bus: EventBus,
) -> ReviewBundle:
    """Run security + performance in parallel, then regression + dependency."""
    import asyncio

    root = Path(ctx.workspace)
    blobs = _changed_file_blobs(ctx)
    tools = _registry(bus)

    async def _sec() -> SecurityReview:
        if ctx.dry_run and not blobs:
            return SecurityReview(passed=True, notes="dry_run")
        agent = make_security_reviewer()
        tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=45)
        task = (
            f"Workspace: {root}\nChanged/related files:\n{blobs[:12000]}\n\n"
            f"Issue:\n{ctx.issue_text}\n\nJSON security review only."
        )
        try:
            result = await agent_loop(
                agent, task, provider, tools, tctx, model=model, event_bus=bus
            )
            data = _extract_json(result.output or "")
            if data:
                return SecurityReview(
                    passed=bool(data.get("passed", True)),
                    vulnerabilities=list(data.get("vulnerabilities") or [])[:30],
                    notes=str(data.get("notes") or "")[:500],
                )
        except Exception as exc:  # noqa: BLE001
            return SecurityReview(passed=True, notes=f"llm error: {exc}")
        return _heuristic_security(blobs)

    async def _perf() -> PerfReview:
        if ctx.dry_run and not blobs:
            return PerfReview(passed=True, notes="dry_run")
        agent = make_perf_reviewer()
        tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=45)
        task = (
            f"Workspace: {root}\nChanged/related files:\n{blobs[:12000]}\n\n"
            f"Issue:\n{ctx.issue_text}\n\nJSON performance review only."
        )
        try:
            result = await agent_loop(
                agent, task, provider, tools, tctx, model=model, event_bus=bus
            )
            data = _extract_json(result.output or "")
            if data:
                return PerfReview(
                    passed=bool(data.get("passed", True)),
                    issues=list(data.get("issues") or [])[:30],
                    notes=str(data.get("notes") or "")[:500],
                )
        except Exception as exc:  # noqa: BLE001
            return PerfReview(passed=True, notes=f"llm error: {exc}")
        return _heuristic_perf(blobs)

    async def _reg() -> RegressionReview:
        mem_block, _ = _memory_context(ctx)
        agent = make_regression_detector()
        tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=40)
        task = (
            f"Memory of past fixes/failures:\n{mem_block}\n\n"
            f"Current changes:\n{blobs[:8000]}\n\nIssue:\n{ctx.issue_text}\n\nJSON only."
        )
        try:
            result = await agent_loop(
                agent, task, provider, tools, tctx, model=model, event_bus=bus
            )
            data = _extract_json(result.output or "")
            if data:
                return RegressionReview(
                    regression_risk=str(data.get("regression_risk") or "none"),
                    warnings=list(data.get("warnings") or [])[:20],
                    notes=str(data.get("notes") or "")[:500],
                )
        except Exception as exc:  # noqa: BLE001
            return RegressionReview(regression_risk="none", notes=f"llm error: {exc}")
        # Heuristic: if memory has failures on same files, elevate risk
        risk = "none"
        warnings: list[dict[str, Any]] = []
        for h in ctx.memory_hits:
            if h.get("kind") == "failure":
                risk = "low"
                warnings.append(
                    {
                        "past_issue": h.get("title"),
                        "past_fix": h.get("summary"),
                        "current_change": ", ".join(ctx.changed_files[:5]),
                        "risk": "low — similar failure memory exists",
                        "recommendation": "Double-check edge cases from past failure",
                    }
                )
        return RegressionReview(regression_risk=risk, warnings=warnings)

    async def _dep() -> DependencyReview:
        agent = make_dependency_analyzer()
        tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=40)
        intel_notes = ""
        if ctx.context and ctx.context.intelligence:
            intel_notes = json.dumps(ctx.context.intelligence)[:2000]
        task = (
            f"Workspace: {root}\nFiles: {ctx.changed_files}\n"
            f"Intelligence: {intel_notes}\n\nIssue:\n{ctx.issue_text}\n\nJSON only."
        )
        try:
            result = await agent_loop(
                agent, task, provider, tools, tctx, model=model, event_bus=bus
            )
            data = _extract_json(result.output or "")
            if data:
                return DependencyReview(
                    summary=str(data.get("summary") or ""),
                    affected_modules=list(data.get("affected_modules") or [])[:30],
                    external_deps=list(data.get("external_deps") or [])[:30],
                    risk_level=str(data.get("risk_level") or "low"),
                    notes=[str(n) for n in (data.get("notes") or [])][:20],
                )
        except Exception as exc:  # noqa: BLE001
            return DependencyReview(summary=f"llm error: {exc}", risk_level="low")
        mods = list(ctx.changed_files)[:20]
        return DependencyReview(
            summary="Heuristic: modules inferred from changed files",
            affected_modules=mods,
            risk_level="low",
        )

    # Parallel: security + performance (safe — read-only, independent)
    security, performance = await asyncio.gather(_sec(), _perf())
    # Then regression + dependency (also independent; sequential gather still concurrent)
    regression, dependency = await asyncio.gather(_reg(), _dep())

    blocking = False
    if not security.passed:
        blocking = True
    if not performance.passed:
        blocking = True
    if regression.regression_risk == "high":
        blocking = True

    return ReviewBundle(
        security=security,
        performance=performance,
        regression=regression,
        dependency=dependency,
        blocking=blocking,
        notes="reviews complete",
    )


async def stage_pr_draft(
    ctx: WorkflowContext,
    provider: LLMProvider,
    model: str,
    bus: EventBus,
) -> PRDraft:
    """Generate commit message + PR title/body."""
    root = Path(ctx.workspace)
    if ctx.dry_run:
        if ctx.plan and ctx.plan.summary:
            summary = ctx.plan.summary
        elif ctx.classification and ctx.classification.summary:
            summary = ctx.classification.summary
        else:
            summary = "change"
        return PRDraft(
            commit_message=f"fix: {summary}",
            pr_title=summary[:72] or "Aegis fix",
            pr_body="## Summary\n\nDry-run — no code changes.\n",
            related_modules=list(ctx.changed_files)[:10],
            testing_done="dry_run",
        )

    agent = make_pr_generator()
    tools = _registry(bus)
    tctx = ToolContext(workspace_root=root, agent=agent.name, event_bus=bus, timeout=40)
    review_summary = ""
    if ctx.reviews:
        review_summary = json.dumps(ctx.reviews.model_dump(), indent=2)[:2500]
    task = (
        f"Issue:\n{ctx.issue_text}\n\n"
        f"Code summary:\n{ctx.code_summary[:1500]}\n\n"
        f"Changed files: {ctx.changed_files}\n\n"
        f"Tests: passed={ctx.tests.passed if ctx.tests else None}\n\n"
        f"Reviews:\n{review_summary}\n\n"
        "Produce JSON PR draft only."
    )
    result = await agent_loop(agent, task, provider, tools, tctx, model=model, event_bus=bus)
    data = _extract_json(result.output or "")
    if data:
        return PRDraft(
            commit_message=str(data.get("commit_message") or "")[:2000],
            pr_title=str(data.get("pr_title") or "")[:200],
            pr_body=str(data.get("pr_body") or "")[:8000],
            related_modules=list(data.get("related_modules") or [])[:30],
            testing_done=str(data.get("testing_done") or "")[:500],
        )
    summary = (
        (ctx.plan.summary if ctx.plan else "")
        or (ctx.classification.summary if ctx.classification else "")
        or "Aegis autonomous fix"
    )
    body_lines = [
        "## Summary",
        "",
        summary,
        "",
        "## Changed files",
        "",
        *[f"- `{f}`" for f in ctx.changed_files[:30]],
        "",
        "## Test plan",
        "",
        f"Tests passed: {ctx.tests.passed if ctx.tests else 'n/a'}",
        "",
    ]
    if ctx.issue_url:
        body_lines += [f"Closes: {ctx.issue_url}", ""]
    body_lines.append("*Generated by Aegis Engineer*")
    return PRDraft(
        commit_message=f"fix: {summary[:60]}",
        pr_title=summary[:72],
        pr_body="\n".join(body_lines),
        related_modules=list(ctx.changed_files)[:10],
        testing_done=f"pytest passed={ctx.tests.passed if ctx.tests else None}",
    )


def persist_run_memory(ctx: WorkflowContext, *, success: bool) -> str | None:
    """Write solved or failure memory after a run. Returns entry id."""
    if ctx.meta.get("memory_enabled") is False:
        return None
    try:
        from aegis.memory.store import MemoryStore

        # Prefer original workspace for durable memory (not a temp worktree)
        mem_root = ctx.meta.get("original_workspace") or ctx.workspace
        store = MemoryStore(
            mem_root,
            store_dir=str(ctx.meta.get("memory_store_dir") or ".aegis/memory"),
            global_enabled=bool(ctx.meta.get("memory_global", True)),
        )
        clf = ctx.classification.type if ctx.classification else ""
        if success:
            entry = store.record_solved(
                issue_text=ctx.issue_text,
                summary=(
                    (ctx.plan.summary if ctx.plan else None)
                    or (ctx.classification.summary if ctx.classification else None)
                    or "Solved"
                ),
                classification=clf,
                files=ctx.changed_files,
                plan_summary=ctx.plan.summary if ctx.plan else "",
                code_summary=ctx.code_summary,
                tags=[clf] if clf else [],
                also_global=bool(ctx.meta.get("memory_write_global", False)),
            )
            return entry.id
        entry = store.record_failure(
            issue_text=ctx.issue_text,
            approach=ctx.code_summary or (ctx.plan.summary if ctx.plan else "unknown"),
            reason=ctx.error or "workflow failed",
            files=ctx.changed_files,
            classification=clf,
        )
        return entry.id
    except Exception:  # noqa: BLE001
        return None

