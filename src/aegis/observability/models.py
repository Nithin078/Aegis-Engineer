"""Observability trace models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_trace_id() -> str:
    return f"trace_{uuid4().hex[:12]}"


class TraceEvent(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: str  # agent.start|agent.thinking|tool|agent.done|workflow|reasoning|prompt
    agent: str = ""
    phase: str = ""
    message: str = ""
    duration_ms: float | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CostRow(BaseModel):
    agent: str
    tokens: int = 0
    cost_usd: float = 0.0
    iterations: int = 0


class LatencyRow(BaseModel):
    phase: str
    duration_ms: float = 0.0
    count: int = 1


class ToolRow(BaseModel):
    step: int
    tool: str
    agent: str = ""
    duration_ms: float = 0.0
    error: bool = False
    summary: str = ""


class SessionTrace(BaseModel):
    id: str = Field(default_factory=_new_trace_id)
    workspace: str = ""
    workflow: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    success: bool | None = None
    events: list[TraceEvent] = Field(default_factory=list)
    costs: list[CostRow] = Field(default_factory=list)
    latency: list[LatencyRow] = Field(default_factory=list)
    tools: list[ToolRow] = Field(default_factory=list)
    prompts: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    totals: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)

    def recompute_totals(self) -> None:
        token_sum = sum(c.tokens for c in self.costs)
        cost_sum = sum(c.cost_usd for c in self.costs)
        # also sum from events if costs empty
        if not self.costs:
            for e in self.events:
                if e.tokens:
                    token_sum += e.tokens
                if e.cost_usd:
                    cost_sum += e.cost_usd
        lat_sum = sum(r.duration_ms for r in self.latency)
        if not self.latency and self.finished_at and self.started_at:
            lat_sum = (self.finished_at - self.started_at).total_seconds() * 1000
        self.totals = {
            "tokens": token_sum,
            "cost_usd": round(cost_sum, 6),
            "duration_ms": round(lat_sum, 1),
            "tool_calls": len(self.tools),
            "events": len(self.events),
            "agents": len({c.agent for c in self.costs if c.agent}),
        }
