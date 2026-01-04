"""Help screen modal for uptop.

This module provides:
- HelpScreen: A modal overlay showing all keybindings and help information
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from uptop import __version__


class HelpContent(Static):
    """Static widget containing help content."""

    DEFAULT_CSS = """
    HelpContent {
        width: 100%;
        height: auto;
        padding: 1 2;
    }
    """


class HelpScreen(ModalScreen[None]):
    """Modal screen showing keybindings and help information.

    This screen displays all available keybindings organized by scope
    (global vs process pane). It can be dismissed with Escape or ?.

    Attributes:
        BINDINGS: Key bindings for dismissing the help screen
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("?", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $background;
        border: solid $accent;
        padding: 0;
    }

    HelpScreen .help-title {
        dock: top;
        width: 100%;
        height: 3;
        background: $accent;
        color: $background;
        text-align: center;
        padding: 1 0;
        text-style: bold;
    }

    HelpScreen .help-section {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    HelpScreen .section-header {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    HelpScreen .keybinding-row {
        width: 100%;
        height: 1;
    }

    HelpScreen .key {
        width: 12;
        text-style: bold;
        color: $warning;
    }

    HelpScreen .description {
        width: 1fr;
        color: $foreground;
    }

    HelpScreen .footer-text {
        dock: bottom;
        width: 100%;
        height: 2;
        text-align: center;
        color: $foreground-muted;
        padding: 0 2;
        border-top: solid $border;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the help screen layout.

        Yields:
            Widgets that make up the help screen
        """
        with Container():
            yield Label(f"uptop v{__version__} Help", classes="help-title")

            with Vertical(classes="help-section"):
                yield Label("Global Keybindings", classes="section-header")
                yield self._keybinding_row("q", "Quit application")
                yield self._keybinding_row("?", "Show/hide this help")
                yield self._keybinding_row("r", "Refresh all panes")
                yield self._keybinding_row("Tab", "Focus next pane")
                yield self._keybinding_row("Shift+Tab", "Focus previous pane")
                yield self._keybinding_row("1-5", "Jump to pane by number")

            with Vertical(classes="help-section"):
                yield Label("Process Pane", classes="section-header")
                yield self._keybinding_row("/", "Filter processes")
                yield self._keybinding_row("s", "Cycle sort column")
                yield self._keybinding_row("k", "Kill selected process")
                yield self._keybinding_row("t", "Toggle tree view")

            with Vertical(classes="help-section"):
                yield Label("Navigation", classes="section-header")
                yield self._keybinding_row("Up/Down", "Move selection")
                yield self._keybinding_row("PgUp/PgDn", "Page up/down")
                yield self._keybinding_row("Home/End", "Jump to start/end")
                yield self._keybinding_row("Click", "Select/focus with mouse")

            yield Label("Press Escape or ? to close", classes="footer-text")

    def _keybinding_row(self, key: str, description: str) -> Static:
        """Create a keybinding row with key and description.

        Args:
            key: The key or key combination
            description: Description of the action

        Returns:
            A Static widget containing the formatted keybinding row
        """
        # Use Rich markup for formatting within the Static widget
        content = f"[bold yellow]{key:<12}[/bold yellow] {description}"
        return Static(content, classes="keybinding-row")
