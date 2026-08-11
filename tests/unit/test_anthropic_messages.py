"""Unit tests for Anthropic message conversion (no network)."""

from __future__ import annotations

from aegis.providers.anthropic_provider import (
    _openai_tools_to_anthropic,
    _to_anthropic_messages,
)


def test_system_and_user_conversion() -> None:
    system, msgs = _to_anthropic_messages(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
    )
    assert system == "You are helpful."
    assert msgs == [{"role": "user", "content": "Hi"}]


def test_tool_calls_and_results() -> None:
    system, msgs = _to_anthropic_messages(
        [
            {"role": "user", "content": "read file"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read",
                            "arguments": '{"path": "a.py"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "print(1)",
            },
        ]
    )
    assert system is None
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"][0]["type"] == "tool_use"
    assert msgs[1]["content"][0]["name"] == "read"
    assert msgs[2]["role"] == "user"
    assert msgs[2]["content"][0]["type"] == "tool_result"


def test_tools_schema() -> None:
    tools = _openai_tools_to_anthropic(
        [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                },
            }
        ]
    )
    assert tools is not None
    assert tools[0]["name"] == "read"
    assert "path" in tools[0]["input_schema"]["properties"]
