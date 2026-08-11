"""Tests for provider helpers and mock provider."""

from __future__ import annotations

import pytest

from aegis.config.schema import ProviderConfig
from aegis.providers.factory import resolve_api_key
from aegis.providers.mock import MockProvider, text_response
from aegis.providers.openai_provider import estimate_cost_usd
from aegis.providers.types import TokenUsage


def test_estimate_cost() -> None:
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=0, total_tokens=1_000_000)
    cost = estimate_cost_usd("gpt-4o", usage)
    assert cost == pytest.approx(2.50)


def test_resolve_api_key_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    cfg = ProviderConfig(
        default="openai",
        api_keys={"openai": "env:OPENAI_API_KEY"},
    )
    assert resolve_api_key("openai", cfg) == "sk-test-123"


def test_resolve_api_key_literal() -> None:
    cfg = ProviderConfig(api_keys={"anthropic": "sk-literal"})
    assert resolve_api_key("anthropic", cfg) == "sk-literal"


@pytest.mark.asyncio
async def test_mock_provider_streams_text() -> None:
    provider = MockProvider(responses=[text_response("hello world")])
    chunks = []
    async for c in provider.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="mock-model",
    ):
        chunks.append(c)
    text = "".join(c.delta or "" for c in chunks)
    assert text == "hello world"
    assert provider.calls[0]["model"] == "mock-model"
