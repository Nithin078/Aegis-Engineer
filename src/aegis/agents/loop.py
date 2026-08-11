"""Core agent loop: LLM → tools → repeat until done."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from aegis.agents.base import Agent, AgentResult
from aegis.bus.events import EventType
from aegis.bus.pubsub import EventBus
from aegis.providers.base import LLMProvider
from aegis.providers.types import ChatChunk, TokenUsage, ToolCallDelta
from aegis.tools.base import ToolContext
from aegis.tools.registry import ToolRegistry

OnText = Callable[[str], Awaitable[None] | None]


async def agent_loop(
    agent: Agent,
    task: str,
    provider: LLMProvider,
    tools: ToolRegistry,
    ctx: ToolContext,
    *,
    model: str,
    event_bus: EventBus | None = None,
    prior_messages: list[dict[str, Any]] | None = None,
    on_text: OnText | None = None,
) -> AgentResult:
    """Run the shared agent loop until the model stops calling tools or max iterations."""
    bus = event_bus or ctx.event_bus or tools.event_bus

    system_prompt = agent.system_prompt
    try:
        from aegis.plugins.hooks import get_hooks

        system_prompt = await get_hooks().transform_system_prompt(agent.name, system_prompt)
    except Exception:  # noqa: BLE001
        pass

    messages: list[dict[str, Any]] = list(prior_messages or [])
    if not messages:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]
    elif messages[0].get("role") != "system":
        messages = [{"role": "system", "content": system_prompt}, *messages]
        if task:
            messages.append({"role": "user", "content": task})
    elif task and (len(messages) == 1 or messages[-1].get("role") != "user"):
        messages.append({"role": "user", "content": task})

    total_usage = TokenUsage()
    total_cost = 0.0
    tool_call_count = 0
    last_text = ""

    await bus.publish(
        EventType.AGENT_START,
        {"agent": agent.name, "task": task[:500]},
    )

    tool_schemas = tools.llm_schemas(agent.permissions)
    # ctx should use agent name for permission checks
    ctx.agent = agent.name
    ctx.timeout = agent.tool_timeout
    if ctx.event_bus is None:
        ctx.event_bus = bus

    for iteration in range(agent.max_iterations):
        await bus.publish(
            EventType.AGENT_THINKING,
            {"agent": agent.name, "iteration": iteration + 1, "model": model},
        )
        try:
            from aegis.observability.collector import get_active_collector

            col = get_active_collector()
            if col is not None:
                col.record_prompt(
                    agent=agent.name,
                    model=model,
                    messages=messages,
                    iteration=iteration + 1,
                )
        except Exception:  # noqa: BLE001
            pass

        text_parts: list[str] = []
        tool_acc: dict[int, ToolCallDelta] = {}
        turn_usage = TokenUsage()
        turn_cost = 0.0
        finish_reason: str | None = None

        try:
            stream = provider.chat(
                messages=messages,
                model=model,
                tools=tool_schemas or None,
                stream=True,
            )
            async for chunk in stream:
                await _handle_chunk(
                    chunk,
                    text_parts,
                    tool_acc,
                    on_text,
                )
                if chunk.usage:
                    turn_usage = turn_usage + chunk.usage
                if chunk.cost_usd:
                    turn_cost += chunk.cost_usd
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
        except Exception as exc:  # noqa: BLE001
            await bus.publish(
                EventType.AGENT_ERROR,
                {"agent": agent.name, "error": str(exc)},
            )
            return AgentResult(
                output=last_text or str(exc),
                messages=messages,
                iterations=iteration + 1,
                error=str(exc),
                input_tokens=total_usage.input_tokens,
                output_tokens=total_usage.output_tokens,
                total_tokens=total_usage.total_tokens,
                cost_usd=total_cost,
                tool_calls=tool_call_count,
            )

        total_usage = total_usage + turn_usage
        total_cost += turn_cost
        content = "".join(text_parts)
        if content:
            last_text = content

        tool_calls = _finalize_tool_calls(tool_acc)

        # Prefer "" over null — Groq and some OpenAI-compatible APIs reject null content.
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments or "{}",
                    },
                }
                for i, tc in enumerate(tool_calls)
            ]
        messages.append(assistant_msg)

        if not tool_calls:
            await bus.publish(
                EventType.AGENT_DONE,
                {
                    "agent": agent.name,
                    "iterations": iteration + 1,
                    "tokens": total_usage.total_tokens,
                    "cost_usd": total_cost,
                    "finish_reason": finish_reason,
                },
            )
            return AgentResult(
                output=content or last_text,
                messages=messages,
                iterations=iteration + 1,
                input_tokens=total_usage.input_tokens,
                output_tokens=total_usage.output_tokens,
                total_tokens=total_usage.total_tokens,
                cost_usd=total_cost,
                tool_calls=tool_call_count,
            )

        # Execute tools
        for tc in tool_calls:
            tool_call_count += 1
            name = tc.name
            try:
                params = json.loads(tc.arguments or "{}")
                if not isinstance(params, dict):
                    params = {"value": params}
            except json.JSONDecodeError:
                params = {}
                result_output = f"Invalid tool arguments JSON: {tc.arguments}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id or "call_unknown",
                        "content": result_output,
                    }
                )
                continue

            result = await tools.execute(name, params, ctx)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id or f"call_{tool_call_count}",
                    "content": result.output,
                }
            )

    await bus.publish(
        EventType.AGENT_ERROR,
        {"agent": agent.name, "error": "max_iterations_exceeded"},
    )
    return AgentResult(
        output=last_text or "Max iterations reached",
        messages=messages,
        iterations=agent.max_iterations,
        error="max_iterations_exceeded",
        input_tokens=total_usage.input_tokens,
        output_tokens=total_usage.output_tokens,
        total_tokens=total_usage.total_tokens,
        cost_usd=total_cost,
        tool_calls=tool_call_count,
    )


async def _handle_chunk(
    chunk: ChatChunk,
    text_parts: list[str],
    tool_acc: dict[int, ToolCallDelta],
    on_text: OnText | None,
) -> None:
    if chunk.delta:
        text_parts.append(chunk.delta)
        if on_text is not None:
            maybe = on_text(chunk.delta)
            if maybe is not None:
                import inspect

                if inspect.isawaitable(maybe):
                    await maybe

    if chunk.tool_call:
        idx = chunk.tool_call.index
        existing = tool_acc.get(idx)
        if existing is None:
            tool_acc[idx] = chunk.tool_call.model_copy()
            return
        if chunk.tool_call.id:
            existing.id = chunk.tool_call.id
        if chunk.tool_call.name:
            existing.name = chunk.tool_call.name
        if chunk.tool_call.arguments:
            new_args = chunk.tool_call.arguments
            old_args = existing.arguments or ""
            # Full snapshot (grows as prefix) or raw delta fragment
            if new_args.startswith(old_args):
                existing.arguments = new_args
            elif old_args.startswith(new_args):
                pass
            else:
                existing.arguments = old_args + new_args


def _finalize_tool_calls(tool_acc: dict[int, ToolCallDelta]) -> list[ToolCallDelta]:
    if not tool_acc:
        return []
    return [tool_acc[i] for i in sorted(tool_acc.keys()) if tool_acc[i].name]
