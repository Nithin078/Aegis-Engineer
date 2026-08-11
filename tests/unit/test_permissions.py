"""Tests for the permission engine."""

from __future__ import annotations

from aegis.config.schema import PermissionRule, PermissionsConfig
from aegis.permissions.engine import PermissionDecision, PermissionEngine


def _engine(
    trust_mode: str = "interactive",
    default: str = "ask",
    rules: list[PermissionRule] | None = None,
) -> PermissionEngine:
    return PermissionEngine(
        PermissionsConfig(
            default=default,  # type: ignore[arg-type]
            trust_mode=trust_mode,  # type: ignore[arg-type]
            rules=rules
            or [
                PermissionRule(tool="read", agent="*", level="allow"),
                PermissionRule(tool="write", agent="coder", level="allow"),
                PermissionRule(tool="write", agent="reviewer", level="deny"),
                PermissionRule(tool="bash", agent="coder", level="ask"),
                PermissionRule(tool="bash", agent="tester", level="allow"),
            ],
        )
    )


def test_exact_and_wildcard_rules() -> None:
    eng = _engine()
    assert eng.resolve("read", "anyone") is PermissionDecision.ALLOW
    assert eng.resolve("write", "coder") is PermissionDecision.ALLOW
    assert eng.resolve("write", "reviewer") is PermissionDecision.DENY
    assert eng.resolve("bash", "coder") is PermissionDecision.ASK
    assert eng.resolve("unknown", "x") is PermissionDecision.ASK


def test_specific_agent_beats_wildcard() -> None:
    eng = PermissionEngine(
        PermissionsConfig(
            default="deny",
            rules=[
                PermissionRule(tool="bash", agent="*", level="deny"),
                PermissionRule(tool="bash", agent="tester", level="allow"),
            ],
        )
    )
    assert eng.resolve("bash", "tester") is PermissionDecision.ALLOW
    assert eng.resolve("bash", "coder") is PermissionDecision.DENY


def test_yolo_converts_ask_to_allow() -> None:
    eng = _engine(trust_mode="yolo")
    assert eng.resolve("bash", "coder") is PermissionDecision.ALLOW
    # deny still deny
    assert eng.resolve("write", "reviewer") is PermissionDecision.DENY


def test_ci_converts_ask_to_deny() -> None:
    eng = _engine(trust_mode="ci")
    assert eng.resolve("bash", "coder") is PermissionDecision.DENY
    assert eng.resolve("read", "x") is PermissionDecision.ALLOW


def test_readonly_blocks_write_and_bash() -> None:
    eng = _engine(trust_mode="readonly")
    assert eng.resolve("read", "coder", ["read"]) is PermissionDecision.ALLOW
    assert eng.resolve("glob", "coder", ["read"]) is PermissionDecision.ALLOW
    assert eng.resolve("grep", "coder", ["read"]) is PermissionDecision.ALLOW
    assert eng.resolve("write", "coder", ["write"]) is PermissionDecision.DENY
    assert eng.resolve("edit", "coder", ["write"]) is PermissionDecision.DENY
    assert eng.resolve("bash", "tester", ["shell"]) is PermissionDecision.DENY


def test_is_allowed() -> None:
    eng = _engine()
    assert eng.is_allowed("read", "x") is True
    assert eng.is_allowed("bash", "coder") is False  # ask is not auto-allow
