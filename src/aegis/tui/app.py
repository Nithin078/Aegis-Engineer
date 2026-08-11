"""Textual application for Aegis Engineer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, RichLog, Static

from aegis import __version__
from aegis.bus.events import EventType
from aegis.tui.backend import HttpTuiBackend, TuiBackend
from aegis.tui.widgets import PermissionModal, StatusBar


class AegisApp(App[None]):
    """Minimal chat TUI."""

    TITLE = "Aegis Engineer"
    SUB_TITLE = f"v{__version__}"
    CSS = """
    Screen {
        layout: vertical;
    }
    #chat-log {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        scrollbar-gutter: stable;
    }
    #hint {
        height: auto;
        color: $text-muted;
        padding: 0 1;
    }
    #prompt {
        dock: bottom;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
    ]

    def __init__(
        self,
        *,
        workspace: Path | None = None,
        model: str | None = None,
        provider: str | None = None,
        trust_mode: str | None = None,
        server_url: str | None = None,
    ) -> None:
        super().__init__()
        self.workspace = (workspace or Path.cwd()).resolve()
        self.server_url = server_url

        if server_url:
            self.backend: TuiBackend | HttpTuiBackend = HttpTuiBackend(
                server_url,
                workspace=self.workspace,
            )
        else:
            self.backend = TuiBackend(
                workspace=self.workspace,
                model=model,
                provider=provider,
                trust_mode=trust_mode or "interactive",
                ask_handler=self._ask_permission,
            )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            f"Workspace: {self.workspace}  ·  "
            f"Enter send  ·  Ctrl+L clear  ·  Ctrl+C quit",
            id="hint",
        )
        yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
        yield Input(
            placeholder="Ask Aegis to help with this codebase…",
            id="prompt",
        )
        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold cyan]Aegis Engineer[/] — autonomous software engineering")
        if self.server_url:
            log.write(f"[dim]Mode: HTTP client → {self.server_url}[/]")
        else:
            log.write("[dim]Mode: in-process (same engine as `aegis run`)[/]")

        ok, detail = self.backend.ensure_api_key()
        if not ok:
            log.write(
                f"[red]No API key configured.[/] {detail}\n"
                "Set keys in [b]~/.config/aegis/.env[/] then restart."
            )
            self._set_status("error: no API key")
        else:
            try:
                sid = self.backend.create_session("TUI session")
                log.write(f"[dim]Session {sid}[/]")
                self._set_status(self._status_line(idle=True))
            except Exception as exc:  # noqa: BLE001
                log.write(f"[red]Failed to create session:[/] {exc}")
                self._set_status(f"error: {exc}")

        self.query_one("#prompt", Input).focus()

    def _status_line(self, *, idle: bool, extra: str = "") -> str:
        sid = self.backend.session_id or "—"
        model = getattr(self.backend, "model_name", "—")
        provider = getattr(self.backend, "provider_name", "—")
        state = "idle" if idle else "thinking…"
        base = f"{state}  ·  {provider}/{model}  ·  session {sid}"
        return f"{base}  ·  {extra}" if extra else base

    def _set_status(self, text: str) -> None:
        self.query_one("#status", StatusBar).set_status(text)

    def action_clear_chat(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        log.write("[dim]Chat cleared.[/]")

    @on(Input.Submitted, "#prompt")
    def handle_submit(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        if not text:
            return
        event.input.value = ""
        if text in {"/quit", "/exit", ":q"}:
            self.exit()
            return
        if text == "/clear":
            self.action_clear_chat()
            return
        self.run_chat(text)

    async def _ask_permission(self, tool: str, agent: str, params: dict) -> bool:
        """Show modal and wait for Allow/Deny."""
        return await self.push_screen_wait(PermissionModal(tool, agent, params))

    @work(exclusive=True)
    async def run_chat(self, prompt: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold green]you[/]  {prompt}")
        self._set_status(self._status_line(idle=False))

        stream_parts: list[str] = []
        tools_seen = 0

        def on_token(delta: str) -> None:
            stream_parts.append(delta)

        def on_event(event_type: str, data: dict[str, Any]) -> None:
            nonlocal tools_seen
            if event_type in (EventType.AGENT_TOOL_CALL, "agent.tool_call"):
                tools_seen += 1
                tool = data.get("tool", "?")
                # Schedule UI update on the app
                self.call_later(log.write, f"[dim yellow]  ↳ tool {tool}[/]")
            elif event_type in (EventType.AGENT_TOOL_RESULT, "agent.tool_result"):
                if data.get("error"):
                    self.call_later(log.write, "[dim red]  ↳ tool failed[/]")

        try:
            result = await self.backend.chat(
                prompt,
                on_token=on_token,
                on_event=on_event,
            )
        except Exception as exc:  # noqa: BLE001
            log.write(f"[red]Error:[/] {exc}")
            self._set_status(self._status_line(idle=True, extra=str(exc)))
            return

        text = "".join(stream_parts) or (result.get("output") or "")
        if text:
            log.write(f"[bold blue]aegis[/]\n{text}")
        else:
            log.write("[bold blue]aegis[/] [dim](no text output)[/]")

        if result.get("error"):
            log.write(f"[red]({result['error']})[/]")

        tokens = result.get("tokens") or 0
        cost = result.get("cost_usd") or 0.0
        tools = result.get("tool_calls") or tools_seen
        self._set_status(
            self._status_line(
                idle=True,
                extra=f"tokens={tokens} cost=${cost:.4f} tools={tools}",
            )
        )


def run_tui(
    *,
    workspace: Path | None = None,
    model: str | None = None,
    provider: str | None = None,
    trust_mode: str | None = None,
    server_url: str | None = None,
) -> None:
    """Launch the Textual TUI (blocking)."""
    app = AegisApp(
        workspace=workspace,
        model=model,
        provider=provider,
        trust_mode=trust_mode,
        server_url=server_url,
    )
    app.run()
