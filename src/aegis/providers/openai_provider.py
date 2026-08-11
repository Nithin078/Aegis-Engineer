"""OpenAI (and OpenAI-compatible) chat provider."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from aegis.providers.base import LLMProvider
from aegis.providers.retry import LLMError, RateLimitError
from aegis.providers.types import ChatChunk, TokenUsage, ToolCallDelta

# Approximate USD / 1M tokens (input, output) for observability.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "o1": (15.00, 60.00),
    "o3": (10.00, 40.00),
    "llama-3.3-70b": (0.59, 0.79),
    "llama-3.1-8b": (0.05, 0.08),
}


def estimate_cost_usd(model: str, usage: TokenUsage) -> float:
    key = model.split("/")[-1].lower()
    for name, (inp, out) in _PRICE_PER_MTOK.items():
        if name in key:
            return (usage.input_tokens * inp + usage.output_tokens * out) / 1_000_000
    return (usage.input_tokens * 1.0 + usage.output_tokens * 3.0) / 1_000_000


def _is_groq(api_base: str | None) -> bool:
    if not api_base:
        return False
    return "groq.com" in api_base.lower()


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make messages safe for strict OpenAI-compatible servers."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        m = dict(msg)
        role = m.get("role")
        # Groq rejects null content on assistant messages
        if role == "assistant" and m.get("content") is None:
            m["content"] = ""
        if role == "tool" and m.get("content") is None:
            m["content"] = ""
        out.append(m)
    return out


def _format_api_error(exc: BaseException) -> str:
    """Extract a readable message from OpenAI SDK / HTTP errors."""
    parts = [str(exc)]
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("failed_generation") or err
            parts.append(f"details={msg}")
        else:
            parts.append(f"body={body}")
    elif body is not None:
        parts.append(f"body={body}")
    return " | ".join(parts)


class OpenAIProvider(LLMProvider):
    """Chat completions via the official OpenAI Python SDK.

    Also works with OpenAI-compatible servers (Ollama, vLLM, Azure, Groq, proxies)
    when ``api_base`` is set.
    """

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        max_retries: int = 3,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key or "no-key"
        self.api_base = api_base
        self.max_retries = max_retries
        self.timeout = timeout

    def _client(self) -> Any:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": 0,  # we handle retries ourselves
        }
        if self.api_base:
            kwargs["base_url"] = self.api_base
        return AsyncOpenAI(**kwargs)

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
        # Strip provider prefix if present (openai/gpt-4o → gpt-4o)
        model_id = model.split("/", 1)[-1] if model.startswith("openai/") else model
        groq = _is_groq(self.api_base)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": _normalize_messages(messages),
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            # Groq is more reliable with one tool call at a time
            if groq:
                kwargs["parallel_tool_calls"] = False
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        # stream_options is OpenAI-specific; Groq often rejects it
        if stream and not groq:
            kwargs["stream_options"] = {"include_usage": True}

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
                # On Groq tool-call generation failure, retry once without tools
                msg = str(exc).lower()
                if (
                    tools
                    and attempt == 0
                    and ("failed to call a function" in msg or "failed_generation" in msg)
                ):
                    # Fall through to text-only so the user gets *something*
                    kwargs.pop("tools", None)
                    kwargs.pop("tool_choice", None)
                    kwargs.pop("parallel_tool_calls", None)
                    last_error = exc
                    continue
                raise LLMError(_format_api_error(exc)) from exc

        detail = _format_api_error(last_error) if last_error else str(last_error)
        raise LLMError(
            f"OpenAI-compatible provider exhausted retries: {detail}"
        ) from last_error

    async def _stream_once(
        self,
        kwargs: dict[str, Any],
        model: str,
    ) -> AsyncIterator[ChatChunk]:
        client = self._client()
        if kwargs.get("stream"):
            stream = await client.chat.completions.create(**kwargs)
            tool_acc: dict[int, ToolCallDelta] = {}
            async for part in stream:
                for chunk in _parse_openai_stream_part(part, model, tool_acc):
                    yield chunk
        else:
            response = await client.chat.completions.create(**kwargs)
            for chunk in _parse_openai_complete(response, model):
                yield chunk


def _is_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return "ratelimit" in name or "rate limit" in msg or "429" in msg


def _usage_from_openai(usage_obj: Any) -> TokenUsage | None:
    if usage_obj is None:
        return None
    inp = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
    out = int(getattr(usage_obj, "completion_tokens", 0) or 0)
    return TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=inp + out)


def _parse_openai_stream_part(
    part: Any,
    model: str,
    tool_acc: dict[int, ToolCallDelta],
) -> list[ChatChunk]:
    chunks: list[ChatChunk] = []
    usage = _usage_from_openai(getattr(part, "usage", None))
    choices = getattr(part, "choices", None) or []

    if not choices:
        if usage:
            chunks.append(
                ChatChunk(usage=usage, cost_usd=estimate_cost_usd(model, usage))
            )
        return chunks

    choice = choices[0]
    delta = getattr(choice, "delta", None)
    finish = getattr(choice, "finish_reason", None)

    if delta is not None:
        content = getattr(delta, "content", None)
        if content:
            chunks.append(ChatChunk(delta=content, finish_reason=finish))

        for tc in getattr(delta, "tool_calls", None) or []:
            idx = int(getattr(tc, "index", 0) or 0)
            acc = tool_acc.get(idx) or ToolCallDelta(index=idx)
            if getattr(tc, "id", None):
                acc.id = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    acc.name = fn.name
                if getattr(fn, "arguments", None):
                    acc.arguments = (acc.arguments or "") + fn.arguments
            tool_acc[idx] = acc
            chunks.append(ChatChunk(tool_call=acc.model_copy(), finish_reason=finish))

        if finish and not content and not getattr(delta, "tool_calls", None):
            chunks.append(ChatChunk(finish_reason=finish))

    if usage:
        chunks.append(
            ChatChunk(
                usage=usage,
                cost_usd=estimate_cost_usd(model, usage),
                finish_reason=finish,
            )
        )
    return chunks


def _parse_openai_complete(response: Any, model: str) -> list[ChatChunk]:
    chunks: list[ChatChunk] = []
    usage = _usage_from_openai(getattr(response, "usage", None))
    cost = estimate_cost_usd(model, usage) if usage else 0.0
    choices = getattr(response, "choices", None) or []
    if not choices:
        if usage:
            chunks.append(ChatChunk(usage=usage, cost_usd=cost, finish_reason="stop"))
        return chunks

    message = choices[0].message
    finish = choices[0].finish_reason
    if message.content:
        chunks.append(ChatChunk(delta=message.content, finish_reason=finish))

    for i, tc in enumerate(getattr(message, "tool_calls", None) or []):
        args = tc.function.arguments if tc.function else ""
        if isinstance(args, dict):
            args = json.dumps(args)
        chunks.append(
            ChatChunk(
                tool_call=ToolCallDelta(
                    id=tc.id or f"call_{i}",
                    name=tc.function.name if tc.function else "",
                    arguments=args or "",
                    index=i,
                ),
                finish_reason=finish,
            )
        )

    if usage:
        chunks.append(ChatChunk(usage=usage, cost_usd=cost, finish_reason=finish))
    return chunks
