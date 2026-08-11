"""Provider listing route."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from aegis.providers.factory import resolve_api_key
from aegis.server.deps import get_state

_KNOWN = [
    {
        "name": "openai",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o1", "o3"],
        "notes": "Also used for Groq / OpenRouter / any OpenAI-compatible base URL",
    },
    {
        "name": "anthropic",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
    },
    {
        "name": "ollama",
        "models": ["llama3.2", "qwen2.5-coder:7b"],
        "notes": "Local OpenAI-compatible server",
    },
    {
        "name": "groq",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "notes": "OpenAI-compatible via api.groq.com",
    },
]


async def list_providers(request: Request) -> JSONResponse:
    state = get_state(request)
    cfg = state.config.provider
    providers = []
    for item in _KNOWN:
        name = item["name"]
        key = resolve_api_key(name if name != "groq" else "openai", cfg)
        if name == "ollama":
            auth = True
        elif name == "groq":
            auth = bool(key)
        else:
            auth = bool(resolve_api_key(name, cfg))
        providers.append(
            {
                "name": name,
                "models": item["models"],
                "auth_configured": auth,
                "notes": item.get("notes"),
                "is_default": name == cfg.default or (name == "openai" and cfg.default == "openai"),
            }
        )
    return JSONResponse(
        {
            "default": cfg.default,
            "model": cfg.model,
            "providers": providers,
        }
    )
