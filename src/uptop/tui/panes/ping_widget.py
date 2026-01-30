"""Ping Widget for uptop TUI.

This module provides a Textual widget for displaying ping monitoring metrics including:
- Host name/IP
- Current latency (min/avg/max)
- Packet loss percentage
- Status (ok/warning/critical)
- Sparkline history of latencies
- Consecutive failure count
- Jitter

The widget supports multiple display modes:
- MICRO: Single line summary
- MINIMIZED: Table with basic metrics
- MEDIUM: Detailed table with sparklines
- MAXIMIZED: Full details with all metrics
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.console import RenderableType
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from uptop.models.base import DisplayMode
from uptop.tui.widgets.sparkline import Sparkline

if TYPE_CHECKING:
    from uptop.plugins.ping_models import PingData


def get_status_color(status: str) -> str:
    """Get color for a ping status.

    Args:
        status: Status string ("ok", "warning", "critical", "unreachable")

    Returns:
        Color name for rich styling
    """
    status_colors = {
        "ok": "green",
        "warning": "yellow",
        "critical": "red",
        "unreachable": "bright_black",
        "dns_failed": "magenta",
    }
    return status_colors.get(status, "white")


def format_latency(latency_ms: float | None) -> str:
    """Format latency for display.

    Args:
        latency_ms: Latency in milliseconds (None if unavailable)

    Returns:
        Formatted string with unit
    """
    if latency_ms is None:
        return "N/A"
    if latency_ms >= 1000:
        return f"{latency_ms / 1000:.2f}s"
    return f"{latency_ms:.1f}ms"


class PingWidget(Widget):
    """Widget for displaying ping monitoring data.

    Supports multiple display modes for different levels of detail.

    Attributes:
        data: Current ping data
        display_mode: Current display mode
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    PingWidget {
        width: 100%;
        height: 100%;
    }

    PingWidget Static {
        width: 100%;
        height: auto;
    }
    """

    data: reactive[PingData | None] = reactive(None)
    display_mode: reactive[DisplayMode] = reactive(DisplayMode.MEDIUM)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the ping widget.

        Args:
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        """Compose the widget."""
        yield Static(id="ping-content")

    def update_data(self, data: PingData, mode: DisplayMode | None = None) -> None:
        """Update the widget with new data.

        Args:
            data: New ping data to display
            mode: Optional display mode override
        """
        self.data = data
        if mode is not None:
            self.display_mode = mode

    def watch_data(self, new_data: PingData | None) -> None:
        """React to data changes."""
        self._refresh_display()

    def watch_display_mode(self, new_mode: DisplayMode) -> None:
        """React to display mode changes."""
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display based on current data and mode."""
        if not self.is_mounted:
            return

        try:
            content = self.query_one("#ping-content", Static)

            if self.data is None or not self.data.hosts:
                content.update("[dim]No ping data available[/dim]")
                return

            if self.display_mode == DisplayMode.MICRO:
                content.update(self._render_micro())
            elif self.display_mode == DisplayMode.MINIMIZED:
                content.update(self._render_minimized())
            elif self.display_mode == DisplayMode.MAXIMIZED:
                content.update(self._render_maximized())
            else:  # MEDIUM (default)
                content.update(self._render_medium())

        except Exception:
            pass

    def _render_micro(self) -> RenderableType:
        """Render MICRO mode: single line summary.

        Returns:
            Rich renderable for single line display
        """
        if not self.data or not self.data.hosts:
            return Text("Ping: No data")

        # Count statuses
        ok_count = sum(1 for r in self.data.hosts if r.alert_level == "ok")
        warning_count = sum(1 for r in self.data.hosts if r.alert_level == "warning")
        critical_count = sum(1 for r in self.data.hosts if r.alert_level == "critical")
        down_count = sum(1 for r in self.data.hosts if r.status in ["down", "dns_failed", "timeout", "unreachable"])

        parts = [Text("Ping: ", style="bold")]

        if ok_count > 0:
            parts.append(Text(f"{ok_count} OK", style="green"))
            parts.append(Text(" "))

        if warning_count > 0:
            parts.append(Text(f"{warning_count} WARN", style="yellow"))
            parts.append(Text(" "))

        if critical_count > 0:
            parts.append(Text(f"{critical_count} CRIT", style="red"))
            parts.append(Text(" "))

        if down_count > 0:
            parts.append(Text(f"{down_count} DOWN", style="bright_black"))

        return Text.assemble(*parts)

    def _render_minimized(self) -> RenderableType:
        """Render MINIMIZED mode: compact table.

        Returns:
            Rich Table with basic metrics
        """
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Host", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True)
        table.add_column("Latency", justify="right", no_wrap=True)
        table.add_column("Loss", justify="right", no_wrap=True)

        for result in self.data.hosts:
            # Use alert_level for status display
            status_color = get_status_color(result.alert_level)
            status_text = Text(result.status.upper(), style=status_color)
            latency_text = format_latency(result.current_latency_ms)
            loss_text = f"{result.packet_loss_percent:.1f}%"

            table.add_row(
                result.host,
                status_text,
                latency_text,
                loss_text,
            )

        return table

    def _render_medium(self) -> RenderableType:
        """Render MEDIUM mode: detailed table with sparklines.

        Returns:
            Rich Table with detailed metrics
        """
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Host", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True, style="bold")
        table.add_column("Latency", justify="right")
        table.add_column("Min/Avg/Max", justify="right")
        table.add_column("Loss", justify="right")
        table.add_column("History", no_wrap=True)

        for result in self.data.hosts:
            status_style = get_status_color(result.alert_level)
            status_text = Text(result.status[:4].upper(), style=status_style)

            latency = format_latency(result.current_latency_ms)
            min_val = format_latency(result.min_latency_ms)
            avg_val = format_latency(result.avg_latency_ms)
            max_val = format_latency(result.max_latency_ms)
            loss = f"{result.packet_loss_percent:.1f}%"

            # Generate sparkline from history
            history_values = [h.latency_ms for h in result.history if h.latency_ms is not None]
            if history_values:
                sparkline_chars = self._generate_sparkline(history_values, width=20)
                sparkline_text = Text(sparkline_chars, style=status_style)
            else:
                sparkline_text = Text("─" * 20, style="dim")

            table.add_row(
                result.host,
                status_text,
                latency,
                f"{min_val}/{avg_val}/{max_val}",
                loss,
                sparkline_text,
            )

        return table

    def _render_maximized(self) -> RenderableType:
        """Render MAXIMIZED mode: full details.

        Returns:
            Rich Table with all available metrics
        """
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Host", no_wrap=True)
        table.add_column("Status", justify="center", style="bold")
        table.add_column("Current", justify="right")
        table.add_column("Min/Avg/Max", justify="right")
        table.add_column("Jitter", justify="right")
        table.add_column("Loss %", justify="right")
        table.add_column("Failures", justify="right")
        table.add_column("History", no_wrap=True)

        for result in self.data.hosts:
            status_style = get_status_color(result.alert_level)
            status_text = Text(result.status.upper(), style=status_style)

            current = format_latency(result.current_latency_ms)
            min_val = format_latency(result.min_latency_ms)
            avg_val = format_latency(result.avg_latency_ms)
            max_val = format_latency(result.max_latency_ms)
            jitter = format_latency(result.jitter_ms)
            loss = f"{result.packet_loss_percent:.1f}%"
            failures = str(result.consecutive_failures)

            # Generate sparkline
            history_values = [h.latency_ms for h in result.history if h.latency_ms is not None]
            if history_values:
                sparkline_chars = self._generate_sparkline(history_values, width=25)
                sparkline_text = Text(sparkline_chars, style=status_style)
            else:
                sparkline_text = Text("─" * 25, style="dim")

            table.add_row(
                result.host,
                status_text,
                current,
                f"{min_val}/{avg_val}/{max_val}",
                jitter,
                loss,
                failures,
                sparkline_text,
            )

        return table

    def _generate_sparkline(self, values: list[float], width: int = 20) -> str:
        """Generate a sparkline from latency values.

        Args:
            values: List of latency values in ms
            width: Width of sparkline in characters

        Returns:
            String with sparkline characters
        """
        if not values:
            return "─" * width

        # Take last N values
        recent_values = values[-width:] if len(values) > width else values

        # Sparkline characters (8 levels)
        chars = "▁▂▃▄▅▆▇█"

        if len(recent_values) == 1:
            # Single value, use middle character
            return chars[len(chars) // 2] * width

        min_val = min(recent_values)
        max_val = max(recent_values)

        if max_val == min_val:
            # All values are the same
            return chars[len(chars) // 2] * len(recent_values)

        # Normalize and map to characters
        sparkline = ""
        for val in recent_values:
            normalized = (val - min_val) / (max_val - min_val)
            char_idx = int(normalized * (len(chars) - 1))
            sparkline += chars[char_idx]

        # Pad if needed
        if len(sparkline) < width:
            sparkline += " " * (width - len(sparkline))

        return sparkline
