"""Anthropic Claude chat provider."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from aegis.providers.base import LLMProvider
from aegis.providers.retry import LLMError, RateLimitError
from aegis.providers.types import ChatChunk, TokenUsage, ToolCallDelta

_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-4-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-sonnet": (3.00, 15.00),
    "claude-haiku": (0.80, 4.00),
}


def estimate_cost_usd(model: str, usage: TokenUsage) -> float:
    key = model.split("/")[-1].lower()
    for name, (inp, out) in _PRICE_PER_MTOK.items():
        if name in key:
            return (usage.input_tokens * inp + usage.output_tokens * out) / 1_000_000
    return (usage.input_tokens * 3.0 + usage.output_tokens * 15.0) / 1_000_000


def _to_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert OpenAI-style messages to Anthropic format."""
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            if isinstance(content, str) and content:
                system_parts.append(content)
            continue

        if role == "tool":
            # Anthropic tool results are user messages with tool_result blocks
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id") or "",
                            "content": content or "",
                        }
                    ],
                }
            )
            continue

        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            if content:
                blocks.append({"type": "text", "text": content})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                args_raw = fn.get("arguments") or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id") or "call_0",
                        "name": fn.get("name") or "",
                        "input": args if isinstance(args, dict) else {"value": args},
                    }
                )
            out.append({"role": "assistant", "content": blocks or content or ""})
            continue

        # user
        out.append({"role": "user", "content": content or ""})

    system = "\n\n".join(system_parts) if system_parts else None
    return system, out


def _openai_tools_to_anthropic(
    tools: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    converted: list[dict[str, Any]] = []
    for t in tools:
        fn = t.get("function") or t
        converted.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return converted


class AnthropicProvider(LLMProvider):
    """Chat completions via the official Anthropic Python SDK."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_retries: int = 3,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout

    def _client(self) -> Any:
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self.api_key, timeout=self.timeout, max_retries=0)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        model_id = model.split("/", 1)[-1] if model.startswith("anthropic/") else model
        system, anth_messages = _to_anthropic_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": anth_messages,
            "max_tokens": max_tokens or 4096,
            "stream": stream,
        }
        if system:
            kwargs["system"] = system
        anth_tools = _openai_tools_to_anthropic(tools)
        if anth_tools:
            kwargs["tools"] = anth_tools
        if temperature is not None:
            kwargs["temperature"] = temperature

        last_error: BaseException | None = None
        for attempt in range(self.max_retries):
            try:
                async for chunk in self._stream_once(kwargs, model_id):
                    yield chunk
                return
            except RateLimitError as exc:
                last_error = exc
                if attempt >= self.max_retries - 1:
                    break
                await asyncio.sleep(2**attempt)
            except Exception as exc:
                if _is_rate_limit(exc):
                    last_error = RateLimitError(str(exc))
                    if attempt >= self.max_retries - 1:
                        break
                    await asyncio.sleep(2**attempt)
                    continue
                raise LLMError(str(exc)) from exc

        raise LLMError(f"Anthropic provider exhausted retries: {last_error}") from last_error

    async def _stream_once(
        self,
        kwargs: dict[str, Any],
        model: str,
    ) -> AsyncIterator[ChatChunk]:
        client = self._client()
        if kwargs.get("stream"):
            stream_kwargs = {k: v for k, v in kwargs.items() if k != "stream"}
            async with client.messages.stream(**stream_kwargs) as stream:
                tool_acc: dict[int, ToolCallDelta] = {}
                index_by_id: dict[str, int] = {}
                next_idx = 0
                async for event in stream:
                    for chunk in _parse_anthropic_event(
                        event, model, tool_acc, index_by_id, next_idx
                    ):
                        # track next index assignments
                        if chunk.tool_call and chunk.tool_call.id:
                            if chunk.tool_call.id not in index_by_id:
                                index_by_id[chunk.tool_call.id] = chunk.tool_call.index
                                next_idx = max(next_idx, chunk.tool_call.index + 1)
                        yield chunk
                # Final message for usage
                final = await stream.get_final_message()
                usage = TokenUsage(
                    input_tokens=int(getattr(final.usage, "input_tokens", 0) or 0),
                    output_tokens=int(getattr(final.usage, "output_tokens", 0) or 0),
                )
                usage.total_tokens = usage.input_tokens + usage.output_tokens
                yield ChatChunk(
                    usage=usage,
                    cost_usd=estimate_cost_usd(model, usage),
                    finish_reason="stop",
                )
        else:
            resp_kwargs = {k: v for k, v in kwargs.items() if k != "stream"}
            message = await client.messages.create(**resp_kwargs)
            for chunk in _parse_anthropic_message(message, model):
                yield chunk


def _is_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return "ratelimit" in name or "rate limit" in msg or "429" in msg


def _parse_anthropic_event(
    event: Any,
    model: str,
    tool_acc: dict[int, ToolCallDelta],
    index_by_id: dict[str, int],
    next_idx: int,
) -> list[ChatChunk]:
    chunks: list[ChatChunk] = []
    etype = getattr(event, "type", None)

    if etype == "content_block_start":
        block = getattr(event, "content_block", None)
        if block is not None and getattr(block, "type", None) == "tool_use":
            idx = index_by_id.get(block.id, next_idx)
            index_by_id[block.id] = idx
            acc = ToolCallDelta(id=block.id, name=block.name, arguments="", index=idx)
            tool_acc[idx] = acc
            chunks.append(ChatChunk(tool_call=acc.model_copy()))
    elif etype == "content_block_delta":
        delta = getattr(event, "delta", None)
        if delta is None:
            return chunks
        dtype = getattr(delta, "type", None)
        if dtype == "text_delta":
            text = getattr(delta, "text", None)
            if text:
                chunks.append(ChatChunk(delta=text))
        elif dtype == "input_json_delta":
            partial = getattr(delta, "partial_json", "") or ""
            # Attach to the most recent tool acc for this event index
            block_index = getattr(event, "index", 0)
            # Find tool by block index — use last tool if mapping unclear
            if tool_acc:
                # content block index may match tool order
                idx = block_index if block_index in tool_acc else max(tool_acc.keys())
                acc = tool_acc[idx]
                acc.arguments = (acc.arguments or "") + partial
                chunks.append(ChatChunk(tool_call=acc.model_copy()))
    elif etype == "message_delta":
        delta = getattr(event, "delta", None)
        stop = getattr(delta, "stop_reason", None) if delta else None
        if stop:
            reason = "tool_calls" if stop == "tool_use" else stop
            chunks.append(ChatChunk(finish_reason=reason))

    return chunks


def _parse_anthropic_message(message: Any, model: str) -> list[ChatChunk]:
    chunks: list[ChatChunk] = []
    text_parts: list[str] = []
    tool_idx = 0
    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
        elif btype == "tool_use":
            chunks.append(
                ChatChunk(
                    tool_call=ToolCallDelta(
                        id=block.id,
                        name=block.name,
                        arguments=json.dumps(block.input or {}),
                        index=tool_idx,
                    ),
                    finish_reason="tool_calls",
                )
            )
            tool_idx += 1

    if text_parts:
        chunks.insert(0, ChatChunk(delta="".join(text_parts), finish_reason="stop"))

    usage = TokenUsage(
        input_tokens=int(getattr(message.usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(message.usage, "output_tokens", 0) or 0),
    )
    usage.total_tokens = usage.input_tokens + usage.output_tokens
    chunks.append(
        ChatChunk(
            usage=usage,
            cost_usd=estimate_cost_usd(model, usage),
            finish_reason=getattr(message, "stop_reason", "stop"),
        )
    )
    return chunks
