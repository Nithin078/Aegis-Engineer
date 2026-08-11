"""General-purpose chat agent for free-form tasks (`aegis run`)."""

from __future__ import annotations

from aegis.agents.base import Agent

CHAT_SYSTEM_PROMPT = """\
You are Aegis Engineer, an autonomous software engineering assistant.

You help users understand, modify, and improve codebases.
You have tools to read and search files, edit code, run shell commands,
and fetch public web pages (webfetch).

Guidelines:
1. Prefer minimal, focused changes.
2. Read relevant files before editing.
3. Use tools when you need repository facts; do not invent file contents.
4. Use webfetch for public docs/URLs (not private or local network hosts).
5. When done, give a clear concise summary of what you found or changed.
6. Stay within the workspace; do not attempt path escapes.

Available tools: read, write, edit, glob, grep, bash, graph_query, codesearch, \
webfetch (subject to permissions).
"""


def create_chat_agent(
    *,
    model: str | None = None,
    max_iterations: int = 20,
    tool_timeout: float = 30.0,
    system_prompt: str | None = None,
) -> Agent:
    """Create the default chat agent configuration."""
    return Agent(
        name="chat",
        system_prompt=system_prompt or CHAT_SYSTEM_PROMPT,
        model=model,
        permissions=["read", "write", "shell", "network"],
        max_iterations=max_iterations,
        tool_timeout=tool_timeout,
    )
