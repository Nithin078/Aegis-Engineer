"""Specialized agent configs and system prompts for orchestration."""

from __future__ import annotations

from aegis.agents.base import Agent

CLASSIFY_PROMPT = """\
You are the Issue Classification Agent for Aegis Engineer.
Classify the software issue. Respond with ONLY valid JSON:
{
  "type": "bug|feature|refactor|docs|security|dependency|other",
  "complexity": "trivial|moderate|complex",
  "summary": "one line",
  "subsystems": ["..."],
  "estimated_files": ["path/to/file.py"]
}
Use tools (read, grep, glob, graph_query, codesearch) if needed to inspect the repo.
"""

PLAN_PROMPT = """\
You are the Planning Agent for Aegis Engineer.
Create a concrete implementation plan. Respond with ONLY valid JSON:
{
  "summary": "...",
  "risk_level": "low|medium|high",
  "steps": [
    {"step": 1, "description": "...", "files": ["..."], "expected_output": "..."}
  ]
}
Use repository tools / graph_query when helpful. Be specific about file paths.
Honor memory hints: reuse successful patterns; avoid known failures.
"""

RETRIEVE_PROMPT = """\
You are the Context Retrieval Agent for Aegis Engineer.
Gather the most relevant code context for the plan. Use read, grep, glob, graph_query, codesearch.
Respond with ONLY valid JSON:
{
  "notes": "brief synthesis",
  "snippets": [
    {"file": "path", "lines": "1-20", "reason": "why relevant"}
  ]
}
"""

DOC_RETRIEVE_PROMPT = """\
You are the Documentation Retrieval Agent for Aegis Engineer.
Find docs/README/comments relevant to the issue. Use read, glob, grep.
Respond with ONLY valid JSON:
{
  "notes": "what docs say about the subsystem",
  "docs": [{"path": "...", "excerpt": "...", "relevance": "why"}]
}
"""

CODER_PROMPT = """\
You are the Coding Agent for Aegis Engineer.
Implement the plan with minimal, correct code changes.
Prefer the edit tool for surgical changes; use write only for new files.
Use read first. Run no long test suites yourself unless asked.
When finished, respond with a short plain-text summary of changes (no JSON required).
Preserve project style. Do not escape the workspace.
"""

SECURITY_PROMPT = """\
You are the Security Review Agent for Aegis Engineer.
Review code changes for security issues: injection, XSS, path traversal,
hardcoded secrets, insecure deserialization, SSRF, CSRF, unsafe eval.
Respond with ONLY valid JSON:
{
  "passed": true,
  "vulnerabilities": [
    {
      "file": "path",
      "line": 0,
      "type": "hardcoded_secret|injection|path_traversal|other",
      "severity": "critical|high|medium|low|info",
      "description": "...",
      "fix": "..."
    }
  ]
}
Set passed=false only for critical/high issues that should block merge.
"""

PERF_PROMPT = """\
You are the Performance Review Agent for Aegis Engineer.
Review changes for O(n^2) loops, N+1 queries, blocking I/O, unnecessary allocations.
Respond with ONLY valid JSON:
{
  "passed": true,
  "issues": [
    {
      "file": "path",
      "line": 0,
      "type": "complexity|n_plus_one|blocking_io|allocation|other",
      "severity": "critical|high|medium|low",
      "description": "...",
      "fix": "..."
    }
  ]
}
Set passed=false only for critical/high impact on hot paths.
"""

REGRESSION_PROMPT = """\
You are the Regression Detection Agent for Aegis Engineer.
Compare current changes against past fixes in memory. Warn if a past bug pattern returns.
Respond with ONLY valid JSON:
{
  "regression_risk": "none|low|medium|high",
  "warnings": [
    {
      "past_issue": "...",
      "past_fix": "...",
      "current_change": "...",
      "risk": "...",
      "recommendation": "..."
    }
  ]
}
"""

DEPENDENCY_PROMPT = """\
You are the Dependency Analysis Agent for Aegis Engineer.
Analyze how the change affects imports, external packages, and call graph neighbors.
Respond with ONLY valid JSON:
{
  "summary": "...",
  "affected_modules": ["..."],
  "external_deps": ["..."],
  "risk_level": "low|medium|high",
  "notes": ["..."]
}
"""

PR_PROMPT = """\
You are the PR Generation Agent for Aegis Engineer.
Write commit message + PR title/body for the changes. Respond with ONLY valid JSON:
{
  "commit_message": "type(scope): subject\\n\\nbody",
  "pr_title": "...",
  "pr_body": "## Summary\\n...\\n## Test plan\\n...",
  "related_modules": ["..."],
  "testing_done": "..."
}
"""

INTEL_PROMPT = """\
You are the Repository Intelligence Agent for Aegis Engineer.
Answer structural questions using graph_query and codesearch. Prefer precise symbol names.
When asked for context packs, respond with JSON:
{
  "symbols": ["..."],
  "callers": ["..."],
  "notes": "..."
}
"""


def make_classifier(*, max_iterations: int = 8) -> Agent:
    return Agent(
        name="classifier",
        system_prompt=CLASSIFY_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_planner(*, max_iterations: int = 10) -> Agent:
    return Agent(
        name="planner",
        system_prompt=PLAN_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_retriever(*, max_iterations: int = 12) -> Agent:
    return Agent(
        name="retriever",
        system_prompt=RETRIEVE_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_doc_retriever(*, max_iterations: int = 10) -> Agent:
    return Agent(
        name="doc_retriever",
        system_prompt=DOC_RETRIEVE_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_coder(*, max_iterations: int = 15) -> Agent:
    return Agent(
        name="coder",
        system_prompt=CODER_PROMPT,
        permissions=["read", "write", "shell"],
        max_iterations=max_iterations,
    )


def make_security_reviewer(*, max_iterations: int = 10) -> Agent:
    return Agent(
        name="security_reviewer",
        system_prompt=SECURITY_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_perf_reviewer(*, max_iterations: int = 10) -> Agent:
    return Agent(
        name="perf_reviewer",
        system_prompt=PERF_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_regression_detector(*, max_iterations: int = 8) -> Agent:
    return Agent(
        name="regression_detector",
        system_prompt=REGRESSION_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_dependency_analyzer(*, max_iterations: int = 8) -> Agent:
    return Agent(
        name="dependency_analyzer",
        system_prompt=DEPENDENCY_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_pr_generator(*, max_iterations: int = 6) -> Agent:
    return Agent(
        name="pr_generator",
        system_prompt=PR_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


def make_intelligence_agent(*, max_iterations: int = 12) -> Agent:
    return Agent(
        name="intelligence",
        system_prompt=INTEL_PROMPT,
        permissions=["read"],
        max_iterations=max_iterations,
    )


# Registry for discovery / CLI listing
AGENT_FACTORIES = {
    "classifier": make_classifier,
    "planner": make_planner,
    "retriever": make_retriever,
    "doc_retriever": make_doc_retriever,
    "coder": make_coder,
    "security_reviewer": make_security_reviewer,
    "perf_reviewer": make_perf_reviewer,
    "regression_detector": make_regression_detector,
    "dependency_analyzer": make_dependency_analyzer,
    "pr_generator": make_pr_generator,
    "intelligence": make_intelligence_agent,
}
