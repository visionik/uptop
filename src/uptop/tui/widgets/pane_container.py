"""Pane Container Widget for uptop TUI.

This module provides a reusable container widget that wraps pane content with:
- A title bar showing the pane name
- A bordered frame around the content
- Refresh indicator when data is being collected
- Error state display when collection fails
- Stale data indicator when data is old
- Click-to-focus behavior for mouse interaction
- Smooth loading animation with spinner
- Subtle highlight on data changes

The PaneContainer is designed to work with any child widget and is composable
for use in grid layouts.
"""

from enum import Enum
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.events import Click, Resize
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, LoadingIndicator, Static

from uptop.models.base import DisplayMode
from uptop.tui.messages import DisplayModeChanged, PaneResized

# Animation durations (in seconds)
LOADING_SPINNER_FADE = 0.15
DATA_HIGHLIGHT_DURATION = 0.5


class PaneState(str, Enum):
    """States a pane can be in.

    Attributes:
        NORMAL: Normal operation, data is fresh
        LOADING: Data collection is in progress
        ERROR: Data collection failed
        STALE: Data is older than expected (refresh may have failed)
    """

    NORMAL = "normal"
    LOADING = "loading"
    ERROR = "error"
    STALE = "stale"


class PaneTitleBar(Static):
    """Title bar widget for the pane container.

    Displays the pane title on the left and status indicators on the right.
    This is internal to PaneContainer - use PaneContainer directly.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    PaneTitleBar {
        width: 100%;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
        layout: horizontal;
    }

    PaneTitleBar .title-text {
        width: 1fr;
        text-style: bold;
        color: $accent;
    }

    PaneTitleBar .status-indicator {
        width: auto;
        min-width: 3;
        text-align: right;
    }

    PaneTitleBar .status-indicator.loading {
        color: $warning;
    }

    PaneTitleBar .status-indicator.error {
        color: $error;
    }

    PaneTitleBar .status-indicator.stale {
        color: $warning;
    }
    """

    title: reactive[str] = reactive("Untitled")
    state: reactive[PaneState] = reactive(PaneState.NORMAL)

    def __init__(
        self,
        title: str = "Untitled",
        state: PaneState = PaneState.NORMAL,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the title bar.

        Args:
            title: The pane title to display
            state: Initial pane state
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.title = title
        self.state = state

    def compose(self) -> ComposeResult:
        """Compose the title bar with title and status indicator."""
        yield Label(self.title, classes="title-text")
        yield Label(self._get_status_text(), classes="status-indicator")

    def _get_status_text(self) -> str:
        """Get the status indicator text based on current state.

        Returns:
            Status indicator symbol or empty string
        """
        status_map = {
            PaneState.NORMAL: "",
            PaneState.LOADING: "[*]",
            PaneState.ERROR: "[!]",
            PaneState.STALE: "[~]",
        }
        return status_map.get(self.state, "")

    def watch_title(self, new_title: str) -> None:
        """React to title changes.

        Args:
            new_title: The new title value
        """
        if not self.is_mounted:
            return
        try:
            title_label = self.query_one(".title-text", Label)
            title_label.update(new_title)
        except Exception:
            pass  # Widget may not be composed yet

    def watch_state(self, new_state: PaneState) -> None:
        """React to state changes.

        Args:
            new_state: The new state value
        """
        if not self.is_mounted:
            return
        try:
            indicator = self.query_one(".status-indicator", Label)
            indicator.update(self._get_status_text())

            # Update CSS classes for styling
            indicator.remove_class("loading", "error", "stale")
            if new_state != PaneState.NORMAL:
                indicator.add_class(new_state.value)
        except Exception:
            pass  # Widget may not be composed yet


class ErrorDisplay(Static):
    """Error display widget shown when data collection fails.

    Shows an error message with a retry hint.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    ErrorDisplay {
        width: 100%;
        height: 100%;
        content-align: center middle;
        background: $error 10%;
        color: $error;
        padding: 1;
    }

    ErrorDisplay .error-message {
        text-align: center;
        width: 100%;
    }

    ErrorDisplay .retry-hint {
        text-align: center;
        width: 100%;
        color: $text-muted;
        text-style: italic;
    }
    """

    error_message: reactive[str] = reactive("An error occurred")

    def __init__(
        self,
        error_message: str = "An error occurred",
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the error display.

        Args:
            error_message: The error message to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        """Compose the error display with message and retry hint."""
        yield Label(self.error_message, classes="error-message")
        yield Label("Press 'r' to retry", classes="retry-hint")

    def watch_error_message(self, new_message: str) -> None:
        """React to error message changes.

        Args:
            new_message: The new error message
        """
        try:
            message_label = self.query_one(".error-message", Label)
            message_label.update(new_message)
        except Exception:
            # Widget may not be composed yet
            pass


class ContentArea(VerticalScroll):
    """Scrollable content area that holds the actual pane content.

    This container wraps the child widget provided to PaneContainer
    and provides vertical scrolling when content exceeds the available space.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    ContentArea {
        width: 100%;
        height: 1fr;
        padding: 0;
        scrollbar-size: 1 1;
    }

    ContentArea:focus {
        scrollbar-color: $accent;
    }
    """


class LoadingOverlay(Container):
    """Overlay container showing a loading spinner.

    This is displayed over the pane content when data is being refreshed,
    providing visual feedback that an update is in progress.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    LoadingOverlay {
        width: 100%;
        height: 100%;
        align: center middle;
        background: $background 50%;
        layer: loading;
        display: none;
    }

    LoadingOverlay.visible {
        display: block;
    }

    LoadingOverlay LoadingIndicator {
        width: auto;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the loading overlay."""
        yield LoadingIndicator()


class PaneContainer(Widget):
    """A container widget for panes with title bar, border, and status display.

    The PaneContainer provides a consistent visual wrapper for pane content:
    - Title bar with pane name and status indicator
    - Bordered frame using Textual's border styling
    - Loading indicator when data is being refreshed
    - Error display when collection fails
    - Stale data indicator when data is old

    Attributes:
        title: The pane title displayed in the title bar
        refresh_interval: Expected refresh interval in seconds (for stale detection)
        is_loading: Whether data is currently being collected
        has_error: Whether the last collection failed
        error_message: Error message to display when has_error is True
        is_stale: Whether the data is stale (older than expected)

    Example:
        ```python
        class MyApp(App):
            def compose(self) -> ComposeResult:
                with PaneContainer(title="CPU Monitor", refresh_interval=1.0):
                    yield CPUWidget()
        ```
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    PaneContainer {
        width: 100%;
        height: 100%;
        border: solid $primary;
        border-title-color: $accent;
        border-title-style: bold;
        padding: 0;
        layout: vertical;
        layers: content loading;
    }

    PaneContainer:focus {
        border: double $accent;
        border-title-color: $accent;
    }

    PaneContainer:focus-within {
        border: double $accent;
        border-title-color: $accent;
    }

    PaneContainer.focused {
        border: double $accent;
        border-title-color: $accent;
    }

    /* Loading state - no visual change to avoid flashing */
    PaneContainer.loading {
    }

    PaneContainer.error {
        border: solid $error;
    }

    PaneContainer.stale {
        border: dashed $warning;
    }

    /* Data update highlight animation */
    PaneContainer.data-updated {
        background: $accent 10%;
    }

    PaneContainer #pane-body {
        layer: content;
    }

    PaneContainer #loading-overlay {
        layer: loading;
    }
    """

    # Reactive properties
    title: reactive[str] = reactive("Untitled")
    refresh_interval: reactive[float] = reactive(1.0)
    is_loading: reactive[bool] = reactive(False)
    has_error: reactive[bool] = reactive(False)
    error_message: reactive[str] = reactive("")
    is_stale: reactive[bool] = reactive(False)
    display_mode: reactive[DisplayMode] = reactive(DisplayMode.MEDIUM)

    # Whether this container can receive focus (for Tab navigation)
    can_focus: bool = True

    def __init__(
        self,
        title: str = "Untitled",
        refresh_interval: float = 1.0,
        *,
        content: Widget | None = None,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the pane container.

        Args:
            title: The pane title to display in the title bar
            refresh_interval: Expected refresh interval in seconds
            content: Optional child widget to display in the content area
            name: Widget name for CSS/querying
            id: Widget ID for CSS/querying
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.title = title
        self.refresh_interval = refresh_interval
        self._content_widget: Widget | None = content

    def compose(self) -> ComposeResult:
        """Compose the pane container with title bar and content area.

        Yields:
            The title bar, content area, and loading overlay widgets
        """
        # Set border title
        self.border_title = self.title

        with Vertical(id="pane-body"):
            if self.has_error:
                yield ErrorDisplay(
                    error_message=self.error_message or "Data collection failed",
                    id="error-display",
                )
            else:
                with ContentArea(id="content-area"):
                    if self._content_widget is not None:
                        yield self._content_widget
        # Loading overlay (hidden by default)
        yield LoadingOverlay(id="loading-overlay")

    def _get_current_state(self) -> PaneState:
        """Determine the current pane state based on flags.

        Returns:
            The current PaneState value
        """
        if self.has_error:
            return PaneState.ERROR
        if self.is_loading:
            return PaneState.LOADING
        if self.is_stale:
            return PaneState.STALE
        return PaneState.NORMAL

    def _update_state_display(self) -> None:
        """Update the container CSS to reflect current state."""
        state = self._get_current_state()

        # Update container CSS classes
        self.remove_class("loading", "error", "stale")
        if state != PaneState.NORMAL:
            self.add_class(state.value)

        # Update border title with state indicator
        status_map = {
            PaneState.NORMAL: "",
            PaneState.LOADING: " [*]",
            PaneState.ERROR: " [!]",
            PaneState.STALE: " [~]",
        }
        status = status_map.get(state, "")
        self.border_title = f"{self.title}{status}"

    def watch_title(self, new_title: str) -> None:
        """React to title changes.

        Args:
            new_title: The new title value
        """
        self.border_title = new_title

    def watch_is_loading(self, is_loading: bool) -> None:
        """React to loading state changes.

        Args:
            is_loading: Whether data is being collected
        """
        self._update_state_display()

    def watch_has_error(self, has_error: bool) -> None:
        """React to error state changes.

        Args:
            has_error: Whether the last collection failed
        """
        self._update_state_display()

        # Show or hide error display - requires recompose for structure change
        if self.is_mounted:
            self.refresh(recompose=True)

    def watch_error_message(self, new_message: str) -> None:
        """React to error message changes.

        Args:
            new_message: The new error message
        """
        try:
            error_display = self.query_one("#error-display", ErrorDisplay)
            error_display.error_message = new_message
        except Exception:
            pass  # Error display may not exist

    def watch_is_stale(self, is_stale: bool) -> None:
        """React to stale state changes.

        Args:
            is_stale: Whether the data is stale
        """
        self._update_state_display()

    def set_content(self, content: Widget) -> None:
        """Set or replace the content widget.

        If the same widget instance is passed, skips recomposing to preserve
        widget state (like sparkline history).

        Args:
            content: The new content widget to display
        """
        # Skip recompose if it's the same widget instance (preserves history)
        if content is self._content_widget:
            return

        self._content_widget = content
        if self.is_mounted and not self.has_error:
            self.refresh(recompose=True)

    def clear_error(self) -> None:
        """Clear the error state and show content again."""
        self.has_error = False
        self.error_message = ""

    def set_error(self, message: str) -> None:
        """Set the error state with a message.

        Args:
            message: The error message to display
        """
        self.error_message = message
        self.has_error = True

    def start_loading(self) -> None:
        """Mark the pane as loading/refreshing.

        Note: Loading overlay is disabled to avoid visual flashing.
        The state is tracked for potential use by other UI elements.
        """
        self.is_loading = True

    def stop_loading(self) -> None:
        """Mark the pane as done loading.

        Hides the loading spinner.
        """
        self.is_loading = False
        # Hide loading overlay
        try:
            overlay = self.query_one("#loading-overlay", LoadingOverlay)
            overlay.remove_class("visible")
        except Exception:
            pass  # Overlay may not exist

    def _flash_data_updated(self) -> None:
        """Apply a brief highlight effect to indicate data was updated.

        This provides subtle visual feedback that the pane content
        has been refreshed without being distracting.
        """
        # Only apply highlight effect if mounted (app is running)
        if not self.is_mounted:
            return
        self.add_class("data-updated")
        # Remove the highlight class after a brief delay
        self.set_timer(DATA_HIGHLIGHT_DURATION, self._remove_data_highlight)

    def _remove_data_highlight(self) -> None:
        """Remove the data update highlight class."""
        self.remove_class("data-updated")

    def mark_stale(self) -> None:
        """Mark the data as stale."""
        self.is_stale = True

    def mark_fresh(self) -> None:
        """Mark the data as fresh (not stale)."""
        self.is_stale = False

    def on_click(self, event: Click) -> None:
        """Handle click events to focus the pane container.

        When the user clicks on the pane container, it receives focus.
        This provides visual feedback via the focused border style.
        Respects the mouse_enabled configuration from the app.

        Args:
            event: The click event from the mouse
        """
        # Check if mouse is enabled in the app
        if hasattr(self.app, "mouse_enabled") and not self.app.mouse_enabled:
            return

        self.focus()
        # Add focused class for visual feedback
        self.add_class("focused")

    def on_blur(self) -> None:
        """Handle blur events to remove focus styling.

        Called when the pane container loses focus.
        """
        self.remove_class("focused")

    def on_focus(self) -> None:
        """Handle focus events to add focus styling.

        Called when the pane container receives focus.
        """
        self.add_class("focused")

    def on_resize(self, event: Resize) -> None:
        """Handle resize events by posting a message.

        When the pane container is resized, post a PaneResized message
        so the app can re-render the pane with the new dimensions.

        Args:
            event: The resize event with new dimensions
        """
        pane_name = self._get_pane_name()
        if pane_name:
            self.post_message(PaneResized(pane_name, event.size.width, event.size.height))

    def _get_pane_name(self) -> str:
        """Extract pane name from widget ID.

        The widget ID follows the pattern 'pane-{name}', so this
        extracts just the name portion.

        Returns:
            The pane name (e.g., 'cpu', 'memory') or empty string if unavailable
        """
        if self.id and self.id.startswith("pane-"):
            return self.id[5:]
        return ""

    def cycle_display_mode(self) -> DisplayMode:
        """Cycle to the next display mode.

        Cycles through MINIMUM -> MEDIUM -> MAXIMUM -> MINIMUM.
        Posts a DisplayModeChanged message when the mode changes.

        Returns:
            The new display mode after cycling
        """
        self.display_mode = self.display_mode.next()
        return self.display_mode

    def watch_display_mode(self, new_mode: DisplayMode) -> None:
        """React to display mode changes by posting a message.

        Args:
            new_mode: The new display mode
        """
        if self.is_mounted:
            self.post_message(DisplayModeChanged(self._get_pane_name()))
