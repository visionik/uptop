"""Loading Screen for uptop TUI.

This module provides a loading screen shown during application startup
while plugins are being initialized and data is being collected.

The loading screen provides visual feedback to the user and improves
perceived startup performance.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Label, LoadingIndicator, Static


class LoadingMessage(Static):
    """Widget displaying loading status message."""

    DEFAULT_CSS: ClassVar[str] = """
    LoadingMessage {
        width: auto;
        height: auto;
        padding: 1 2;
        text-align: center;
    }

    LoadingMessage .title {
        text-style: bold;
        color: $text;
        text-align: center;
        width: 100%;
    }

    LoadingMessage .subtitle {
        color: $text-muted;
        text-align: center;
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        title: str = "uptop",
        subtitle: str = "Loading...",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the loading message.

        Args:
            title: Main title to display
            subtitle: Subtitle/status message
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._title = title
        self._subtitle = subtitle

    def compose(self) -> ComposeResult:
        """Compose the loading message."""
        yield Label(self._title, classes="title")
        yield Label(self._subtitle, classes="subtitle")


class LoadingScreen(Screen[None]):
    """Loading screen shown during application startup.

    This screen displays:
    - Application title
    - Loading spinner animation
    - Current loading status message

    It provides visual feedback during the potentially slow startup
    process when plugins are being initialized.
    """

    DEFAULT_CSS: ClassVar[str] = """
    LoadingScreen {
        background: $background;
        align: center middle;
    }

    LoadingScreen #loading-container {
        width: auto;
        height: auto;
        padding: 2 4;
        border: round $primary;
        background: $background;
    }

    LoadingScreen LoadingIndicator {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    """

    def __init__(
        self,
        message: str = "Initializing...",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the loading screen.

        Args:
            message: Initial loading status message
            name: Screen name
            id: Screen ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._message = message

    def compose(self) -> ComposeResult:
        """Compose the loading screen layout."""
        with Center():
            with Middle():
                with Static(id="loading-container"):
                    yield LoadingMessage(
                        title="uptop",
                        subtitle=self._message,
                        id="loading-message",
                    )
                    yield LoadingIndicator()

    def update_message(self, message: str) -> None:
        """Update the loading status message.

        Args:
            message: New status message to display
        """
        self._message = message
        try:
            msg_widget = self.query_one("#loading-message", LoadingMessage)
            subtitle = msg_widget.query_one(".subtitle", Label)
            subtitle.update(message)
        except Exception:
            pass  # Widget may not be composed yet
