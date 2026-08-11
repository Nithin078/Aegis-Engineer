"""`aegis run` — non-interactive agent execution."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console

from aegis.agents.chat import create_chat_agent
from aegis.agents.loop import agent_loop
from aegis.bus.pubsub import EventBus
from aegis.config.loader import get_db_path, load_config
from aegis.config.schema import PermissionsConfig
from aegis.permissions.engine import PermissionEngine
from aegis.providers.factory import create_provider, provider_configured, resolve_api_key
from aegis.session.manager import SessionManager
from aegis.tools.base import ToolContext
from aegis.tools.registry import create_default_registry

console = Console(stderr=True)


def run_command(
    prompt: str = typer.Argument(..., help="Task prompt for the agent"),
    model: str | None = typer.Option(None, "--model", "-m", help="Override model"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Override provider"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        help="Workspace root for tools",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    trust_mode: Literal["interactive", "yolo", "readonly", "ci"] | None = typer.Option(
        None,
        "--trust-mode",
        help="Permission trust mode (default: yolo for non-interactive run)",
    ),
    max_iterations: int | None = typer.Option(
        None,
        "--max-iterations",
        help="Max agent loop iterations",
    ),
    title: str | None = typer.Option(None, "--title", help="Session title"),
    session_id: str | None = typer.Option(
        None,
        "--session",
        help="Existing session id to append to (default: create new)",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Print final result as JSON"),
) -> None:
    """Run a one-shot agent task (non-interactive)."""
    try:
        asyncio.run(
            _run_async(
                prompt=prompt,
                model=model,
                provider=provider,
                workspace=workspace,
                trust_mode=trust_mode,
                max_iterations=max_iterations,
                title=title,
                session_id=session_id,
                json_output=json_output,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(code=130) from None
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


async def _run_async(
    *,
    prompt: str,
    model: str | None,
    provider: str | None,
    workspace: Path,
    trust_mode: str | None,
    max_iterations: int | None,
    title: str | None,
    session_id: str | None,
    json_output: bool,
) -> None:
    config = load_config()
    provider_name = provider or config.provider.default
    model_name = model or config.provider.model

    ok, detail = provider_configured(config)
    # Ollama is ok without key; others need key for real calls
    if not ok and provider_name.lower() != "mock":
        key = resolve_api_key(provider_name, config.provider)
        if not key:
            from aegis.config.env import user_env_path

            global_env = user_env_path()
            project_env = Path.cwd() / ".env"
            console.print(
                f"[red]No API key configured for provider '{provider_name}'.[/red]\n"
                f"Add OPENAI_API_KEY (or ANTHROPIC_API_KEY) to one of:\n"
                f"  • Global (all projects): {global_env}\n"
                f"  • This project only:    {project_env}\n"
                f"Or set the env var in your shell. See .env.example in the Aegis repo.\n"
                f"Detail: {detail}"
            )
            raise typer.Exit(code=1)


    # Non-interactive: default to yolo so tools work without a TUI prompt.
    mode = trust_mode or (
        config.permissions.trust_mode
        if config.permissions.trust_mode != "interactive"
        else "yolo"
    )
    if trust_mode is None and config.permissions.trust_mode == "interactive":
        console.print(
            "[dim]Non-interactive run: using trust_mode=yolo "
            "(override with --trust-mode)[/dim]"
        )

    perm_config = PermissionsConfig(
        default=config.permissions.default,
        trust_mode=mode,  # type: ignore[arg-type]
        rules=config.permissions.rules,
    )
    engine = PermissionEngine(perm_config)
    bus = EventBus()
    registry = create_default_registry(permission_engine=engine, event_bus=bus)

    llm = create_provider(config, provider_name=provider_name)
    agent = create_chat_agent(
        model=model_name,
        max_iterations=max_iterations or config.agents.max_iterations,
        tool_timeout=config.agents.tool_timeout,
    )

    session_mgr = SessionManager(get_db_path(config))
    if session_id:
        session = session_mgr.get(session_id)
    else:
        session = session_mgr.create(
            title=title or prompt[:80],
            model=model_name,
            provider=provider_name,
        )
        console.print(f"[dim]Session {session.id}[/dim]")

    session_mgr.add_message(session.id, "user", prompt)

    ctx = ToolContext(
        workspace_root=workspace,
        agent=agent.name,
        event_bus=bus,
        timeout=agent.tool_timeout,
    )

    def on_text(delta: str) -> None:
        if not json_output:
            sys.stdout.write(delta)
            sys.stdout.flush()

    result = await agent_loop(
        agent=agent,
        task=prompt,
        provider=llm,
        tools=registry,
        ctx=ctx,
        model=model_name,
        event_bus=bus,
        on_text=on_text,
    )

    if not json_output and result.output and not result.output.endswith("\n"):
        sys.stdout.write("\n")
        sys.stdout.flush()

    # Persist assistant turn summary + usage on session
    session_mgr.add_message(
        session.id,
        "assistant",
        result.output or "",
        tokens=result.total_tokens or None,
        cost_usd=result.cost_usd or None,
    )
    # Refresh session aggregates (add_message already bumps tokens/cost)

    if json_output:
        import json

        payload = {
            "session_id": session.id,
            "output": result.output,
            "iterations": result.iterations,
            "error": result.error,
            "tokens": {
                "input": result.input_tokens,
                "output": result.output_tokens,
                "total": result.total_tokens,
            },
            "cost_usd": result.cost_usd,
            "tool_calls": result.tool_calls,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        console.print(
            f"\n[dim]session={session.id}  "
            f"iters={result.iterations}  "
            f"tools={result.tool_calls}  "
            f"tokens={result.total_tokens}  "
            f"cost=${result.cost_usd:.4f}"
            f"{'  ERROR=' + result.error if result.error else ''}[/dim]"
        )

    if result.error:
        raise typer.Exit(code=1)
