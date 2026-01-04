"""Filter screen modal for uptop process pane.

This module provides:
- FilterScreen: A modal overlay for filtering processes by name, command, or PID
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static


class FilterScreen(ModalScreen[str | None]):
    """Modal screen for entering process filter text.

    This screen provides a text input for filtering processes by name,
    command line, PID, or username. It returns the filter text on submit
    or None if cancelled.

    Attributes:
        BINDINGS: Key bindings for the filter screen
        current_filter: The current filter text (if any)
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "submit", "Apply", show=True, priority=True),
    ]

    DEFAULT_CSS = """
    FilterScreen {
        align: center middle;
    }

    FilterScreen > Container {
        width: 60;
        height: auto;
        max-height: 15;
        background: $background;
        border: solid $accent;
        padding: 0;
    }

    FilterScreen .filter-title {
        dock: top;
        width: 100%;
        height: 3;
        background: $accent;
        color: $background;
        text-align: center;
        padding: 1 0;
        text-style: bold;
    }

    FilterScreen .filter-content {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    FilterScreen .filter-help {
        width: 100%;
        height: auto;
        color: $text-muted;
        padding: 0 2 1 2;
    }

    FilterScreen Input {
        width: 100%;
        margin: 1 0;
    }

    FilterScreen .footer-text {
        dock: bottom;
        width: 100%;
        height: 2;
        text-align: center;
        color: $foreground-muted;
        padding: 0 2;
        border-top: solid $border;
    }
    """

    def __init__(self, current_filter: str = "") -> None:
        """Initialize the filter screen.

        Args:
            current_filter: The current filter text to pre-populate
        """
        super().__init__()
        self._current_filter = current_filter

    def compose(self) -> ComposeResult:
        """Compose the filter screen layout.

        Yields:
            Widgets that make up the filter screen
        """
        with Container():
            yield Label("Filter Processes", classes="filter-title")

            with Vertical(classes="filter-content"):
                yield Label("Enter filter text (matches name, command, PID, or user):")
                yield Input(
                    value=self._current_filter,
                    placeholder="e.g., python, nginx, 1234",
                    id="filter-input",
                )

            yield Static(
                "Tip: Filter matches process name, command line, PID, or username",
                classes="filter-help",
            )

            yield Label("Enter to apply, Escape to cancel", classes="footer-text")

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        input_widget = self.query_one("#filter-input", Input)
        input_widget.focus()

    def action_cancel(self) -> None:
        """Cancel filtering and close the modal."""
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit the filter text and close the modal."""
        input_widget = self.query_one("#filter-input", Input)
        self.dismiss(input_widget.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission via Enter key.

        Args:
            event: The input submitted event
        """
        self.dismiss(event.value)
