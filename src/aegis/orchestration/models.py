"""Workflow state machine models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowState(StrEnum):
    IDLE = "idle"
    CLASSIFY = "classify"
    PLAN = "plan"
    RETRIEVE = "retrieve"
    CODE = "code"
    ANALYZE = "analyze"
    TEST = "test"
    REVIEW = "review"
    PR = "pr"
    COMPLETE = "complete"
    FAILED = "failed"


class IssueClassification(BaseModel):
    type: str = "bug"  # bug|feature|refactor|docs|security|dependency|other
    complexity: str = "moderate"  # trivial|moderate|complex
    summary: str = ""
    subsystems: list[str] = Field(default_factory=list)
    estimated_files: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    step: int
    description: str
    files: list[str] = Field(default_factory=list)
    expected_output: str = ""


class ImplementationPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)
    risk_level: str = "medium"
    summary: str = ""
    memory_hints: list[str] = Field(default_factory=list)


class ContextBundle(BaseModel):
    snippets: list[dict[str, Any]] = Field(default_factory=list)
    intelligence: dict[str, Any] = Field(default_factory=dict)
    docs: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class AnalysisResult(BaseModel):
    passed: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    command: str | None = None
    output_tail: str = ""


class TestResult(BaseModel):
    passed: bool = True
    total: int = 0
    failed: int = 0
    command: str | None = None
    output_tail: str = ""
    failures: list[str] = Field(default_factory=list)


class SecurityReview(BaseModel):
    passed: bool = True
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class PerfReview(BaseModel):
    passed: bool = True
    issues: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class RegressionReview(BaseModel):
    regression_risk: str = "none"  # none|low|medium|high
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class DependencyReview(BaseModel):
    summary: str = ""
    affected_modules: list[str] = Field(default_factory=list)
    external_deps: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    notes: list[str] = Field(default_factory=list)


class ReviewBundle(BaseModel):
    """Parallel review results after tests."""

    security: SecurityReview | None = None
    performance: PerfReview | None = None
    regression: RegressionReview | None = None
    dependency: DependencyReview | None = None
    blocking: bool = False  # True if any review should fail the pipeline
    notes: str = ""


class PRDraft(BaseModel):
    commit_message: str = ""
    pr_title: str = ""
    pr_body: str = ""
    related_modules: list[str] = Field(default_factory=list)
    testing_done: str = ""


class WorkflowContext(BaseModel):
    issue_text: str
    workspace: str
    dry_run: bool = False
    state: WorkflowState = WorkflowState.IDLE
    retries: int = 0
    max_retries: int = 3
    classification: IssueClassification | None = None
    plan: ImplementationPlan | None = None
    context: ContextBundle | None = None
    code_summary: str = ""
    analysis: AnalysisResult | None = None
    tests: TestResult | None = None
    reviews: ReviewBundle | None = None
    pr_draft: PRDraft | None = None
    memory_hits: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    # Phase 9: isolation / GitHub metadata (JSON-serializable)
    meta: dict[str, Any] = Field(default_factory=dict)
    issue_url: str | None = None
    worktree_path: str | None = None
    worktree_branch: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    pr_url: str | None = None

    def log(self, event: str, **data: Any) -> None:
        self.history.append(
            {
                "ts": datetime.now(UTC).isoformat(),
                "state": self.state.value,
                "event": event,
                **data,
            }
        )


class WorkflowResult(BaseModel):
    state: WorkflowState
    context: WorkflowContext
    success: bool = False
    report_path: str | None = None
