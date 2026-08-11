"""Reusable TUI widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class StatusBar(Static):
    """Footer status: session, model, busy state."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def set_status(self, text: str) -> None:
        self.update(text)


class PermissionModal(ModalScreen[bool]):
    """Ask the user to approve or deny a tool call."""

    DEFAULT_CSS = """
    PermissionModal {
        align: center middle;
    }
    PermissionModal > Vertical {
        width: 70;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    PermissionModal #perm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    PermissionModal #perm-detail {
        margin-bottom: 1;
        color: $text-muted;
    }
    PermissionModal Horizontal {
        height: auto;
        align: right middle;
    }
    PermissionModal Button {
        margin-left: 1;
    }
    """

    def __init__(self, tool: str, agent: str, params: dict) -> None:
        super().__init__()
        self.tool = tool
        self.agent = agent
        self.params = params

    def compose(self) -> ComposeResult:
        detail = str(self.params)
        if len(detail) > 200:
            detail = detail[:197] + "..."
        with Vertical():
            yield Label("Permission required", id="perm-title")
            yield Label(
                f"Agent [b]{self.agent}[/b] wants to run tool [b]{self.tool}[/b]",
                id="perm-msg",
            )
            yield Label(detail, id="perm-detail")
            with Horizontal():
                yield Button("Deny", variant="error", id="deny")
                yield Button("Allow", variant="success", id="allow")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")
