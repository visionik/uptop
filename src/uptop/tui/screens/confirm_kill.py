"""Kill confirmation screen modal for uptop process pane.

This module provides:
- ConfirmKillScreen: A modal overlay for confirming process termination
- KillSignal: Enum for kill signal selection (SIGTERM or SIGKILL)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import signal
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

if TYPE_CHECKING:
    from uptop.plugins.processes import ProcessInfo


class KillSignal(Enum):
    """Signal to send when killing a process."""

    SIGTERM = signal.SIGTERM  # Graceful termination
    SIGKILL = signal.SIGKILL  # Force kill


@dataclass
class KillResult:
    """Result of a kill confirmation dialog."""

    confirmed: bool
    signal: KillSignal
    pid: int


class ConfirmKillScreen(ModalScreen[KillResult | None]):
    """Modal screen for confirming process termination.

    This screen displays process information and provides options to
    terminate the process with SIGTERM (default) or SIGKILL (force).
    It returns a KillResult on confirmation or None if cancelled.

    Attributes:
        BINDINGS: Key bindings for the confirmation screen
        process: The process to be killed
        pid: The PID of the process to be killed
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("y", "confirm_term", "Kill (SIGTERM)", show=True),
        Binding("f", "confirm_kill", "Force (SIGKILL)", show=True),
        Binding("n", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmKillScreen {
        align: center middle;
    }

    ConfirmKillScreen > Container {
        width: 70;
        height: auto;
        max-height: 20;
        background: $background;
        border: solid $error;
        padding: 0;
    }

    ConfirmKillScreen .kill-title {
        dock: top;
        width: 100%;
        height: 3;
        background: $error;
        color: $background;
        text-align: center;
        padding: 1 0;
        text-style: bold;
    }

    ConfirmKillScreen .kill-content {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    ConfirmKillScreen .process-info {
        width: 100%;
        height: auto;
        padding: 1 0;
    }

    ConfirmKillScreen .process-field {
        width: 100%;
        height: 1;
    }

    ConfirmKillScreen .field-label {
        width: 12;
        text-style: bold;
        color: $accent;
    }

    ConfirmKillScreen .field-value {
        width: 1fr;
        color: $foreground;
    }

    ConfirmKillScreen .warning-text {
        width: 100%;
        height: auto;
        color: $warning;
        text-style: bold;
        padding: 1 0;
        text-align: center;
    }

    ConfirmKillScreen .button-row {
        width: 100%;
        height: 3;
        align: center middle;
        padding: 1 0;
    }

    ConfirmKillScreen Button {
        margin: 0 1;
    }

    ConfirmKillScreen .btn-term {
        background: $warning;
    }

    ConfirmKillScreen .btn-kill {
        background: $error;
    }

    ConfirmKillScreen .btn-cancel {
        background: $surface;
    }

    ConfirmKillScreen .footer-text {
        dock: bottom;
        width: 100%;
        height: 2;
        text-align: center;
        color: $foreground-muted;
        padding: 0 2;
        border-top: solid $border;
    }
    """

    def __init__(
        self,
        pid: int,
        process: ProcessInfo | None = None,
    ) -> None:
        """Initialize the kill confirmation screen.

        Args:
            pid: The PID of the process to kill
            process: Optional ProcessInfo with additional details
        """
        super().__init__()
        self._pid = pid
        self._process = process

    def compose(self) -> ComposeResult:
        """Compose the kill confirmation screen layout.

        Yields:
            Widgets that make up the confirmation screen
        """
        with Container():
            yield Label("Kill Process", classes="kill-title")

            with Vertical(classes="kill-content"):
                yield Label("Are you sure you want to kill this process?")

                with Vertical(classes="process-info"):
                    # PID
                    yield Static(
                        f"[bold $accent]PID:         [/bold $accent]{self._pid}",
                        classes="process-field",
                    )

                    # Name
                    name = self._process.name if self._process else "Unknown"
                    yield Static(
                        f"[bold $accent]Name:        [/bold $accent]{name}",
                        classes="process-field",
                    )

                    # User
                    user = self._process.username if self._process else "Unknown"
                    yield Static(
                        f"[bold $accent]User:        [/bold $accent]{user}",
                        classes="process-field",
                    )

                    # Command
                    if self._process and self._process.cmdline:
                        cmd = self._process.cmdline[:60]
                        if len(self._process.cmdline) > 60:
                            cmd += "..."
                    else:
                        cmd = name
                    yield Static(
                        f"[bold $accent]Command:     [/bold $accent]{cmd}",
                        classes="process-field",
                    )

                    # CPU/Memory
                    if self._process:
                        cpu_pct = self._process.cpu_percent
                        mem_pct = self._process.memory_percent
                        yield Static(
                            f"[bold $accent]CPU%:        [/bold $accent]{cpu_pct:.1f}%",
                            classes="process-field",
                        )
                        yield Static(
                            f"[bold $accent]MEM%:        [/bold $accent]{mem_pct:.1f}%",
                            classes="process-field",
                        )

                yield Label("This action cannot be undone!", classes="warning-text")

                with Horizontal(classes="button-row"):
                    yield Button("Kill (y)", variant="warning", id="btn-term", classes="btn-term")
                    yield Button("Force (f)", variant="error", id="btn-kill", classes="btn-kill")
                    yield Button("Cancel (n)", id="btn-cancel", classes="btn-cancel")

            yield Label(
                "y: SIGTERM (graceful) | f: SIGKILL (force) | Escape: Cancel",
                classes="footer-text",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: The button press event
        """
        if event.button.id == "btn-term":
            self.dismiss(KillResult(confirmed=True, signal=KillSignal.SIGTERM, pid=self._pid))
        elif event.button.id == "btn-kill":
            self.dismiss(KillResult(confirmed=True, signal=KillSignal.SIGKILL, pid=self._pid))
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_confirm_term(self) -> None:
        """Confirm kill with SIGTERM (graceful termination)."""
        self.dismiss(KillResult(confirmed=True, signal=KillSignal.SIGTERM, pid=self._pid))

    def action_confirm_kill(self) -> None:
        """Confirm kill with SIGKILL (force kill)."""
        self.dismiss(KillResult(confirmed=True, signal=KillSignal.SIGKILL, pid=self._pid))
