"""Data models for the quality gate."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


class Verdict(StrEnum):
    SAFE = "SAFE TO PUSH"
    NOT_SAFE = "NOT SAFE TO PUSH"


class Finding(BaseModel):
    severity: str = "warning"  # critical | warning | info
    category: str
    message: str
    location: str | None = None  # file:line or path
    detail: str | None = None


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    summary: str = ""
    required: bool = True
    findings: list[Finding] = Field(default_factory=list)
    duration_ms: float = 0.0
    command: str | None = None
    output_tail: str | None = None


class GateReport(BaseModel):
    workspace: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verdict: Verdict = Verdict.NOT_SAFE
    checks: list[CheckResult] = Field(default_factory=list)
    report_md_path: str | None = None
    report_json_path: str | None = None

    def recompute_verdict(self) -> Verdict:
        for check in self.checks:
            if check.required and check.status in (CheckStatus.FAIL, CheckStatus.ERROR):
                self.verdict = Verdict.NOT_SAFE
                return self.verdict
        self.verdict = Verdict.SAFE
        return self.verdict

    def failed_required(self) -> list[CheckResult]:
        return [
            c
            for c in self.checks
            if c.required and c.status in (CheckStatus.FAIL, CheckStatus.ERROR)
        ]

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "created_at": self.created_at.isoformat(),
            "verdict": self.verdict.value,
            "safe": self.verdict is Verdict.SAFE,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "summary": c.summary,
                    "required": c.required,
                    "findings": len(c.findings),
                }
                for c in self.checks
            ],
            "report_md_path": self.report_md_path,
            "report_json_path": self.report_json_path,
        }
