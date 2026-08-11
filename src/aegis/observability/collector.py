"""Collect observability events from the event bus into a SessionTrace."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.observability.models import (
    CostRow,
    LatencyRow,
    SessionTrace,
    ToolRow,
    TraceEvent,
)
from aegis.observability.store import save_trace

_active: ContextVar[TraceCollector | None] = ContextVar("aegis_trace_collector", default=None)


def get_active_collector() -> TraceCollector | None:
    return _active.get()


class TraceCollector:
    """Subscribe to EventBus and build a SessionTrace."""

    def __init__(
        self,
        *,
        workspace: str | Path = "",
        workflow: str = "",
        prompt_logging: bool = True,
        tool_logging: bool = True,
        cost_tracking: bool = True,
    ) -> None:
        self.trace = SessionTrace(
            workspace=str(workspace) if workspace else "",
            workflow=workflow,
        )
        self.prompt_logging = prompt_logging
        self.tool_logging = tool_logging
        self.cost_tracking = cost_tracking
        self._phase_starts: dict[str, float] = {}
        self._agent_starts: dict[str, float] = {}
        self._tool_starts: dict[str, float] = {}
        self._cost_by_agent: dict[str, CostRow] = {}
        self._tool_step = 0
        self._token: object | None = None
        self._bus: EventBus | None = None

    def attach(self, bus: EventBus) -> None:
        self._bus = bus
        bus.subscribe("*", self._on_event)
        self._token = _active.set(self)

    def detach(self) -> None:
        if self._bus is not None:
            try:
                self._bus.unsubscribe("*", self._on_event)
            except Exception:  # noqa: BLE001
                pass
        if self._token is not None:
            try:
                _active.reset(self._token)  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001
                pass
            self._token = None

    def mark_phase(self, phase: str, *, enter: bool = True) -> None:
        if enter:
            self._phase_starts[phase] = time.perf_counter()
            self.reason(f"enter phase {phase}", agent="manager", phase=phase)
        else:
            start = self._phase_starts.pop(phase, None)
            if start is not None:
                ms = (time.perf_counter() - start) * 1000
                self._add_latency(phase, ms)
                self.reason(f"exit phase {phase} ({ms:.0f}ms)", agent="manager", phase=phase)

    def reason(self, message: str, *, agent: str = "", phase: str = "") -> None:
        self.trace.reasoning.append(
            f"[{datetime.now(UTC).strftime('%H:%M:%S')}] "
            f"{(agent or 'system').upper()}: {message}"
        )
        self.trace.events.append(
            TraceEvent(
                kind="reasoning",
                agent=agent,
                phase=phase,
                message=message[:1000],
            )
        )

    def record_prompt(
        self,
        *,
        agent: str,
        model: str,
        messages: list[dict[str, Any]],
        iteration: int = 0,
    ) -> None:
        if not self.prompt_logging:
            return
        summary = []
        for m in messages[-6:]:
            role = m.get("role", "?")
            content = m.get("content") or ""
            if isinstance(content, list):
                content = str(content)[:200]
            summary.append(
                {
                    "role": role,
                    "chars": len(str(content)),
                    "preview": str(content)[:200],
                }
            )
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "agent": agent,
            "model": model,
            "iteration": iteration,
            "messages": summary,
        }
        self.trace.prompts.append(entry)
        self.trace.events.append(
            TraceEvent(
                kind="prompt",
                agent=agent,
                message=f"prompt iter={iteration} model={model}",
                data={"message_count": len(messages)},
            )
        )

    def record_agent_usage(
        self,
        agent: str,
        *,
        tokens: int = 0,
        cost_usd: float = 0.0,
        iterations: int = 0,
    ) -> None:
        if not self.cost_tracking:
            return
        row = self._cost_by_agent.get(agent)
        if row is None:
            row = CostRow(agent=agent)
            self._cost_by_agent[agent] = row
        row.tokens += tokens
        row.cost_usd += cost_usd
        row.iterations += iterations
        self.trace.costs = list(self._cost_by_agent.values())

    def finish(
        self,
        *,
        success: bool | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SessionTrace:
        self.trace.finished_at = datetime.now(UTC)
        if success is not None:
            self.trace.success = success
        if meta:
            self.trace.meta.update(meta)
        # close open phases
        for phase in list(self._phase_starts.keys()):
            self.mark_phase(phase, enter=False)
        self.trace.recompute_totals()
        return self.trace

    def save(self, root: Path | str | None = None) -> Path:
        self.trace.recompute_totals()
        base = Path(root) if root else (
            Path(self.trace.workspace) if self.trace.workspace else Path.cwd()
        )
        return save_trace(self.trace, base)

    def _add_latency(self, phase: str, ms: float) -> None:
        for row in self.trace.latency:
            if row.phase == phase:
                row.duration_ms += ms
                row.count += 1
                return
        self.trace.latency.append(LatencyRow(phase=phase, duration_ms=ms, count=1))

    def _on_event(self, event_type: str, data: dict[str, Any]) -> None:
        agent = str(data.get("agent") or "")
        kind = event_type
        message = ""
        duration_ms = data.get("duration_ms")
        tokens = data.get("tokens")
        cost = data.get("cost_usd")

        if event_type == EventType.AGENT_START or event_type == "agent.start":
            self._agent_starts[agent] = time.perf_counter()
            message = f"start {data.get('task', data.get('workflow', ''))}"[:200]
            if agent:
                self.reason(f"Agent {agent} started", agent=agent)
        elif event_type == EventType.AGENT_THINKING or event_type == "agent.thinking":
            message = f"thinking iter={data.get('iteration')}"
        elif event_type == EventType.AGENT_TOOL_CALL or event_type == "agent.tool_call":
            tool = str(data.get("tool") or "")
            key = f"{agent}:{tool}:{self._tool_step}"
            self._tool_starts[key] = time.perf_counter()
            message = f"tool call {tool}"
        elif event_type == EventType.AGENT_TOOL_RESULT or event_type == "agent.tool_result":
            tool = str(data.get("tool") or "")
            if self.tool_logging:
                self._tool_step += 1
                ms = float(duration_ms or 0)
                if not ms:
                    # best-effort match last start for tool
                    for k, start in list(self._tool_starts.items()):
                        if k.startswith(f"{agent}:{tool}:"):
                            ms = (time.perf_counter() - start) * 1000
                            self._tool_starts.pop(k, None)
                            break
                summary = str(data.get("summary") or data.get("output") or "")[:200]
                self.trace.tools.append(
                    ToolRow(
                        step=self._tool_step,
                        tool=tool,
                        agent=agent,
                        duration_ms=round(ms, 2),
                        error=bool(data.get("error")),
                        summary=summary,
                    )
                )
                duration_ms = ms
            message = f"tool result {tool}"
        elif event_type == EventType.AGENT_DONE or event_type == "agent.done":
            start = self._agent_starts.pop(agent, None)
            if start is not None:
                duration_ms = (time.perf_counter() - start) * 1000
                self._add_latency(f"agent:{agent}", float(duration_ms))
            if tokens or cost:
                self.record_agent_usage(
                    agent,
                    tokens=int(tokens or 0),
                    cost_usd=float(cost or 0),
                    iterations=int(data.get("iterations") or 0),
                )
            message = f"done tokens={tokens} cost={cost}"
            self.reason(
                f"Agent {agent} done (tokens={tokens}, cost={cost})",
                agent=agent,
            )
        elif event_type == EventType.AGENT_ERROR or event_type == "agent.error":
            message = str(data.get("error") or "error")
            self.reason(f"ERROR {agent}: {message}", agent=agent or "system")
        else:
            message = str(data)[:200]

        safe_data = {
            k: v
            for k, v in list(data.items())[:20]
            if k not in {"params", "messages"}
        }
        self.trace.events.append(
            TraceEvent(
                kind=kind,
                agent=agent,
                message=message[:500],
                duration_ms=float(duration_ms) if duration_ms is not None else None,
                tokens=int(tokens) if tokens is not None else None,
                cost_usd=float(cost) if cost is not None else None,
                data=safe_data,
            )
        )


@contextmanager
def collect_trace(
    bus: EventBus,
    *,
    workspace: str | Path = "",
    workflow: str = "",
    prompt_logging: bool = True,
) -> Iterator[TraceCollector]:
    collector = TraceCollector(
        workspace=workspace,
        workflow=workflow,
        prompt_logging=prompt_logging,
    )
    collector.attach(bus)
    try:
        yield collector
    finally:
        collector.detach()
