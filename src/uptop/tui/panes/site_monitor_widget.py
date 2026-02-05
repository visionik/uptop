"""Site Monitor Widget for uptop TUI.

This module provides a Textual widget for displaying website uptime status.
The widget shows:
- Site URL and status (UP/DOWN)
- Response time in milliseconds
- HTTP status code
- Visual indicators for up/down status
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Label

from uptop.models.base import DisplayMode
from uptop.plugins.site_monitor import SiteMonitorData, SiteStatus


def format_response_time(ms: float | None) -> str:
    """Format response time in milliseconds.

    Args:
        ms: Response time in milliseconds

    Returns:
        Formatted string like "123ms" or "--"
    """
    if ms is None:
        return "--"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def format_url(url: str, max_len: int = 30) -> str:
    """Format URL for display, truncating if needed.

    Args:
        url: The URL to format
        max_len: Maximum length before truncation

    Returns:
        Formatted URL string
    """
    # Remove protocol for cleaner display
    display = url.replace("https://", "").replace("http://", "")
    if len(display) > max_len:
        return display[: max_len - 3] + "..."
    return display


class SiteMonitorWidget(Widget):
    """Widget for displaying site monitoring status.

    Displays a table of monitored sites with their status including:
    - Site URL
    - Status indicator (UP/DOWN)
    - HTTP status code
    - Response time
    - Summary of total up/down

    Attributes:
        data: The SiteMonitorData object containing site statuses
    """

    DEFAULT_CSS: ClassVar[str] = """
    SiteMonitorWidget {
        width: 100%;
        height: 100%;
        padding: 0;
    }

    SiteMonitorWidget #site-table {
        width: 100%;
        height: 1fr;
        scrollbar-size: 1 1;
    }

    SiteMonitorWidget #summary-label {
        width: 100%;
        height: 1;
        background: $surface;
        text-align: center;
    }

    SiteMonitorWidget #summary-label.all-up {
        color: $success;
    }

    SiteMonitorWidget #summary-label.some-down {
        color: $error;
    }

    SiteMonitorWidget .micro-label {
        width: 100%;
        height: 100%;
        content-align: center middle;
    }

    SiteMonitorWidget .micro-label.all-up {
        color: $success;
    }

    SiteMonitorWidget .micro-label.some-down {
        color: $error;
    }
    """

    data: reactive[SiteMonitorData | None] = reactive(None)
    _display_mode: reactive[DisplayMode] = reactive(DisplayMode.MINIMIZED)

    def __init__(
        self,
        data: SiteMonitorData | None = None,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the site monitor widget.

        Args:
            data: Initial SiteMonitorData to display
            name: Widget name for CSS/querying
            id: Widget ID for CSS/querying
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.data = data

    def compose(self) -> ComposeResult:
        """Compose the widget based on the current display mode."""
        match self._display_mode:
            case DisplayMode.MICRO:
                # Ultra-compact: single line with up/down count
                if self.data:
                    up = self.data.total_up
                    down = self.data.total_down
                    status_class = "all-up" if down == 0 else "some-down"
                    icon = "✓" if down == 0 else "✗"
                    label = Label(f"Sites {icon} {up}↑ {down}↓", classes=f"micro-label {status_class}")
                else:
                    label = Label("Sites --", classes="micro-label")
                yield label

            case DisplayMode.MINIMIZED | DisplayMode.MEDIUM | DisplayMode.MAXIMIZED:
                yield DataTable(id="site-table")
                yield Label("", id="summary-label")

    def on_mount(self) -> None:
        """Set up the data table when the widget is mounted."""
        if self._display_mode == DisplayMode.MICRO:
            return

        try:
            table = self.query_one("#site-table", DataTable)
        except Exception:
            return

        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("Site", key="url", width=32)
        table.add_column("Status", key="status", width=8)
        table.add_column("Code", key="code", width=5)
        table.add_column("Time", key="time", width=8)

        # Populate with initial data if available
        if self.data is not None:
            self._update_table()

    def watch_data(self, new_data: SiteMonitorData | None) -> None:
        """React to data changes.

        Args:
            new_data: The new SiteMonitorData value
        """
        if self.is_mounted and new_data is not None:
            self._update_table()

    def _format_site_row(self, site: SiteStatus) -> tuple[str, str, str, str]:
        """Format site data as a table row.

        Args:
            site: The site status to format

        Returns:
            Tuple of formatted column values
        """
        url = format_url(site.url)
        status = "✓ UP" if site.is_up else "✗ DOWN"
        code = str(site.status_code) if site.status_code else "--"
        time_str = format_response_time(site.response_time_ms)
        
        return (url, status, code, time_str)

    def _update_table(self) -> None:
        """Update the data table with current data."""
        if self.data is None:
            return

        try:
            table = self.query_one("#site-table", DataTable)
        except Exception:
            return

        # Clear existing rows
        table.clear()

        # Add rows for each site
        for site in self.data.sites:
            row_data = self._format_site_row(site)
            table.add_row(*row_data, key=site.url)

        # Update summary
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary label."""
        if self.data is None:
            return

        try:
            summary = self.query_one("#summary-label", Label)
        except Exception:
            return

        up = self.data.total_up
        down = self.data.total_down
        total = len(self.data.sites)

        if down == 0:
            summary.update(f"All {total} sites UP ✓")
            summary.remove_class("some-down")
            summary.add_class("all-up")
        else:
            summary.update(f"{down}/{total} sites DOWN ✗")
            summary.remove_class("all-up")
            summary.add_class("some-down")

    def update_data(self, data: SiteMonitorData, mode: DisplayMode | None = None) -> None:
        """Update the widget with new site monitoring data.

        Args:
            data: The new SiteMonitorData to display
            mode: Optional display mode to switch to
        """
        if mode is not None and mode != self._display_mode:
            self._display_mode = mode
            self.recompose()
        self.data = data
