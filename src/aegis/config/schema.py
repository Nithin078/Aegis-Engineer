"""Pydantic configuration schema for Aegis Engineer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FallbackProvider(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"


class ProviderConfig(BaseModel):
    default: str = "anthropic"
    model: str = "claude-4-sonnet"
    fallback: FallbackProvider = Field(default_factory=FallbackProvider)
    # Values may be literal keys or "env:VAR_NAME" references.
    api_keys: dict[str, str] = Field(
        default_factory=lambda: {
            "anthropic": "env:ANTHROPIC_API_KEY",
            "openai": "env:OPENAI_API_KEY",
            "google": "env:GOOGLE_API_KEY",
        }
    )


class PermissionRule(BaseModel):
    tool: str
    agent: str = "*"
    level: Literal["allow", "deny", "ask"] = "ask"


class PermissionsConfig(BaseModel):
    default: Literal["allow", "deny", "ask"] = "ask"
    trust_mode: Literal["interactive", "yolo", "readonly", "ci"] = "interactive"
    rules: list[PermissionRule] = Field(
        default_factory=lambda: [
            PermissionRule(tool="read", agent="*", level="allow"),
            PermissionRule(tool="glob", agent="*", level="allow"),
            PermissionRule(tool="grep", agent="*", level="allow"),
            PermissionRule(tool="graph_query", agent="*", level="allow"),
            PermissionRule(tool="write", agent="coder", level="allow"),
            PermissionRule(tool="write", agent="pr_generator", level="allow"),
            PermissionRule(tool="bash", agent="tester", level="allow"),
            PermissionRule(tool="bash", agent="coder", level="ask"),
            PermissionRule(tool="webfetch", agent="doc_retriever", level="allow"),
        ]
    )


class AgentsConfig(BaseModel):
    max_iterations: int = 20
    tool_timeout: float = 30.0
    llm_timeout: float = 120.0
    model_override: dict[str, str] = Field(default_factory=dict)


class IntelligenceConfig(BaseModel):
    build_on_clone: bool = True
    incremental_updates: bool = True
    cache_dir: str = ".aegis/intelligence"
    languages: list[str] = Field(
        default_factory=lambda: ["python", "javascript", "typescript", "go", "rust"]
    )


class MemoryConfig(BaseModel):
    enabled: bool = True
    store_dir: str = ".aegis/memory"
    max_entries_per_repo: int = 1000
    global_memory_enabled: bool = True


class ExecutionConfig(BaseModel):
    sandbox_image: str = "aegis-sandbox:latest"
    timeout: float = 120.0
    mem_limit: str = "512m"


class ObservabilityConfig(BaseModel):
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    prompt_logging: bool = True
    tool_logging: bool = True
    cost_tracking: bool = True


class ServerConfig(BaseModel):
    port: int = 4096
    host: str = "127.0.0.1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


class AegisConfig(BaseModel):
    """Root configuration object for Aegis Engineer."""

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    # Optional absolute path override for the SQLite database.
    db_path: str | None = None

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten nested config into dotted keys for CLI display/set."""
        return _flatten(self.model_dump(mode="json"))


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    items: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            # Keep api_keys as dotted leaf keys: provider.api_keys.openai
            items.update(_flatten(value, path))
        elif isinstance(value, list):
            # Represent lists as JSON-ish strings for flat display.
            items[path] = value
        else:
            items[path] = value
    return items


def set_nested(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a nested dict value from a dotted key (e.g. provider.model)."""
    parts = dotted_key.split(".")
    current: dict[str, Any] = data
    for part in parts[:-1]:
        next_val = current.get(part)
        if not isinstance(next_val, dict):
            next_val = {}
            current[part] = next_val
        current = next_val
    current[parts[-1]] = value


def unset_nested(data: dict[str, Any], dotted_key: str) -> bool:
    """Remove a nested key. Returns True if the key existed."""
    parts = dotted_key.split(".")
    current: dict[str, Any] = data
    stack: list[tuple[dict[str, Any], str]] = []
    for part in parts[:-1]:
        next_val = current.get(part)
        if not isinstance(next_val, dict):
            return False
        stack.append((current, part))
        current = next_val
    leaf = parts[-1]
    if leaf not in current:
        return False
    del current[leaf]
    # Prune empty parent dicts
    for parent, key in reversed(stack):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            del parent[key]
        else:
            break
    return True


def parse_cli_value(raw: str) -> Any:
    """Parse a CLI string value into bool/int/float/str."""
    lowered = raw.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw
