"""Permission checking: tool + agent → allow | deny | ask."""

from __future__ import annotations

from enum import StrEnum

from aegis.config.schema import PermissionRule, PermissionsConfig


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


# Tools considered safe in readonly trust mode.
_READONLY_TOOLS = frozenset(
    {
        "read",
        "glob",
        "grep",
        "codesearch",
        "graph_query",
        "lsp",
    }
)

# Capability tags that imply mutation / dangerous side effects.
_WRITE_CAPABILITIES = frozenset({"write", "shell", "network", "agent"})


class PermissionEngine:
    """Resolve whether an agent may execute a tool under the current rules."""

    def __init__(self, config: PermissionsConfig | None = None) -> None:
        self.config = config or PermissionsConfig()

    def resolve(
        self,
        tool: str,
        agent: str,
        tool_capabilities: list[str] | None = None,
    ) -> PermissionDecision:
        """Return allow/deny/ask for (tool, agent), applying trust mode."""
        capabilities = tool_capabilities or []
        base = self._match_rule(tool, agent)

        mode = self.config.trust_mode
        if mode == "yolo":
            if base is PermissionDecision.ASK:
                return PermissionDecision.ALLOW
            return base

        if mode == "ci":
            if base is PermissionDecision.ASK:
                return PermissionDecision.DENY
            return base

        if mode == "readonly":
            # Only explicitly read-oriented tools; block write capabilities.
            if tool not in _READONLY_TOOLS:
                return PermissionDecision.DENY
            if any(cap in _WRITE_CAPABILITIES for cap in capabilities):
                return PermissionDecision.DENY
            # Read tools: still respect explicit deny rules
            if base is PermissionDecision.DENY:
                return PermissionDecision.DENY
            return PermissionDecision.ALLOW

        # interactive — keep ask as ask
        return base

    def _match_rule(self, tool: str, agent: str) -> PermissionDecision:
        """Find the best matching rule.

        Specificity order:
        1. Exact tool + exact agent
        2. Exact tool + agent wildcard
        3. Tool wildcard + exact agent
        4. Tool wildcard + agent wildcard
        5. Config default level
        """
        rules = self.config.rules
        candidates: list[tuple[int, PermissionRule]] = []

        for rule in rules:
            tool_match = rule.tool == tool or rule.tool == "*"
            agent_match = rule.agent == agent or rule.agent == "*"
            if not (tool_match and agent_match):
                continue
            score = 0
            if rule.tool == tool:
                score += 2
            if rule.agent == agent:
                score += 1
            candidates.append((score, rule))

        if not candidates:
            return PermissionDecision(self.config.default)

        # Highest score wins; if tie, last matching rule in list wins
        candidates.sort(key=lambda item: item[0])
        best_score = candidates[-1][0]
        best_rules = [r for s, r in candidates if s == best_score]
        return PermissionDecision(best_rules[-1].level)

    def is_allowed(
        self,
        tool: str,
        agent: str,
        tool_capabilities: list[str] | None = None,
    ) -> bool:
        """True only when resolve returns ALLOW (ASK is not auto-allowed)."""
        return self.resolve(tool, agent, tool_capabilities) is PermissionDecision.ALLOW
