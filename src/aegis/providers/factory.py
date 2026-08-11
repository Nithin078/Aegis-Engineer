"""Build providers from Aegis configuration."""

from __future__ import annotations

import os
from typing import Any

from aegis.config.schema import AegisConfig, ProviderConfig
from aegis.providers.base import LLMProvider


def resolve_api_key(provider_name: str, config: ProviderConfig) -> str | None:
    """Resolve API key from config (literal or env:VAR) or process env."""
    raw = config.api_keys.get(provider_name)
    if raw:
        if raw.startswith("env:"):
            env_name = raw[4:]
            value = os.environ.get(env_name)
            if value:
                return value
        else:
            return raw

    env_map = {
        "openai": "OPENAI_API_KEY",
        "groq": "OPENAI_API_KEY",  # Groq uses OpenAI-compatible auth header
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "ollama": None,
    }
    env_name = env_map.get(provider_name.lower())
    if env_name:
        return os.environ.get(env_name)
    return os.environ.get("AEGIS_API_KEY")


def create_provider(
    config: AegisConfig | None = None,
    *,
    provider_name: str | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Create a provider for the configured backend."""
    from aegis.config.loader import load_config
    from aegis.providers.anthropic_provider import AnthropicProvider
    from aegis.providers.openai_provider import OpenAIProvider

    cfg = config or load_config()
    name = (provider_name or cfg.provider.default).lower()
    key = api_key if api_key is not None else resolve_api_key(name, cfg.provider)
    timeout = cfg.agents.llm_timeout

    if name in {"anthropic"}:
        return AnthropicProvider(api_key=key, timeout=timeout, **kwargs)

    if name in {"openai", "ollama", "groq"}:
        api_base = kwargs.pop("api_base", None) or os.environ.get("OPENAI_BASE_URL")
        if name == "ollama" and api_base is None:
            api_base = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434/v1")
        if name == "groq" and api_base is None:
            api_base = "https://api.groq.com/openai/v1"
        return OpenAIProvider(
            api_key=key or "ollama",
            api_base=api_base,
            timeout=timeout,
            **kwargs,
        )

    # Default: treat unknown providers as OpenAI-compatible
    api_base = kwargs.pop("api_base", None) or os.environ.get("OPENAI_BASE_URL")
    return OpenAIProvider(api_key=key, api_base=api_base, timeout=timeout, **kwargs)


def provider_configured(config: AegisConfig | None = None) -> tuple[bool, str]:
    """Return (ok, detail) for doctor checks."""
    from aegis.config.loader import load_config

    cfg = config or load_config()
    name = cfg.provider.default
    if name.lower() == "ollama":
        return True, f"provider={name} (local, no API key required)"
    key = resolve_api_key(name, cfg.provider)
    if key:
        return True, f"provider={name} model={cfg.provider.model} (key configured)"
    return False, f"provider={name} model={cfg.provider.model} (no API key found)"
