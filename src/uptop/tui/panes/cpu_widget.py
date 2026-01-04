"""CPU Widget for uptop TUI.

This module provides a Textual widget for displaying CPU metrics including:
- Total CPU usage with progress bar and sparkline history
- Per-core CPU usage with compact progress bars
- Load averages (1/5/15 minute)
- CPU frequency (if available)
- Temperature (if available)

The widget uses color-coded progress bars:
- Green: 0-50% usage
- Yellow: 50-80% usage
- Red: 80-100% usage
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, ClassVar

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from uptop.tui.widgets.sparkline import Sparkline

if TYPE_CHECKING:
    from uptop.plugins.cpu import CPUData


# Color thresholds for CPU usage
THRESHOLD_LOW = 50.0  # 0-50% is green (low usage)
THRESHOLD_MEDIUM = 80.0  # 50-80% is yellow (medium usage)
# Above 80% is red (high usage)


def get_usage_color(usage_percent: float) -> str:
    """Get the color name for a given CPU usage percentage.

    Args:
        usage_percent: CPU usage as a percentage (0-100)

    Returns:
        Color name: 'green', 'yellow', or 'red'
    """
    if usage_percent < THRESHOLD_LOW:
        return "green"
    if usage_percent < THRESHOLD_MEDIUM:
        return "yellow"
    return "red"


def get_usage_style(usage_percent: float) -> Style:
    """Get a Rich Style for a given CPU usage percentage.

    Args:
        usage_percent: CPU usage as a percentage (0-100)

    Returns:
        Rich Style with appropriate foreground color
    """
    return Style(color=get_usage_color(usage_percent))


class CPUProgressBar(Static):
    """A compact horizontal progress bar for CPU usage.

    Displays a fixed-width bar with color-coded fill based on usage level.
    Used for both total and per-core CPU usage display.

    Attributes:
        usage_percent: Current CPU usage percentage (0-100)
        bar_width: Width of the progress bar in characters
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    CPUProgressBar {
        width: auto;
        height: 1;
    }
    """

    usage_percent: reactive[float] = reactive(0.0)
    bar_width: int = 20

    def __init__(
        self,
        usage_percent: float = 0.0,
        bar_width: int = 20,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the CPU progress bar.

        Args:
            usage_percent: Initial CPU usage percentage (0-100)
            bar_width: Width of the bar in characters
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.usage_percent = usage_percent
        self.bar_width = bar_width

    def render(self) -> RenderableType:
        """Render the progress bar as a Rich Text object.

        Returns:
            A Rich Text object displaying the progress bar
        """
        # Calculate filled portion
        filled = int((self.usage_percent / 100.0) * self.bar_width)
        filled = max(0, min(filled, self.bar_width))
        empty = self.bar_width - filled

        # Build the bar with appropriate colors
        color = get_usage_color(self.usage_percent)
        bar = Text()
        bar.append("[", style="dim")
        bar.append("=" * filled, style=color)
        bar.append(" " * empty, style="dim")
        bar.append("]", style="dim")

        return bar


class CoreUsageRow(Static):
    """A single row displaying one CPU core's usage.

    Shows: Core ID, usage percentage, mini progress bar.

    This is designed for compact display when there are many cores.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    CoreUsageRow {
        width: 100%;
        height: 1;
        layout: horizontal;
    }

    CoreUsageRow .core-label {
        width: 8;
        text-align: left;
    }

    CoreUsageRow .core-percent {
        width: 6;
        text-align: right;
    }

    CoreUsageRow .core-bar {
        width: auto;
        margin-left: 1;
    }
    """

    def __init__(
        self,
        core_id: int,
        usage_percent: float,
        freq_mhz: float | None = None,
        temp_celsius: float | None = None,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the core usage row.

        Args:
            core_id: CPU core identifier
            usage_percent: Core usage percentage (0-100)
            freq_mhz: Core frequency in MHz (optional)
            temp_celsius: Core temperature in Celsius (optional)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.core_id = core_id
        self.usage_percent = usage_percent
        self.freq_mhz = freq_mhz
        self.temp_celsius = temp_celsius

    def render(self) -> RenderableType:
        """Render the core usage row.

        Returns:
            A Rich Text object with core info and mini bar
        """
        color = get_usage_color(self.usage_percent)

        # Create the row content
        row = Text()

        # Core label
        row.append(f"Core {self.core_id:2d} ", style="dim")

        # Usage percentage
        row.append(f"{self.usage_percent:5.1f}%", style=color)

        # Mini progress bar (10 chars wide)
        bar_width = 10
        filled = int((self.usage_percent / 100.0) * bar_width)
        filled = max(0, min(filled, bar_width))
        empty = bar_width - filled

        row.append(" [", style="dim")
        row.append("=" * filled, style=color)
        row.append(" " * empty, style="dim")
        row.append("]", style="dim")

        # Optional: frequency
        if self.freq_mhz is not None:
            row.append(f" {self.freq_mhz:4.0f}MHz", style="dim")

        # Optional: temperature
        if self.temp_celsius is not None:
            temp_color = (
                "green"
                if self.temp_celsius < 60
                else ("yellow" if self.temp_celsius < 80 else "red")
            )
            row.append(f" {self.temp_celsius:4.1f}C", style=temp_color)

        return row


class CPUWidget(Widget):
    """Main CPU monitoring widget for uptop TUI.

    Displays comprehensive CPU metrics in a visually appealing format:
    - Total CPU usage with large progress bar and sparkline history
    - Per-core usage with compact progress bars
    - System load averages (1/5/15 minute)
    - CPU frequency information (when available)
    - Temperature readings (when available)

    The widget uses color-coded progress bars:
    - Green (0-50%): Low usage
    - Yellow (50-80%): Medium usage
    - Red (80-100%): High usage

    Attributes:
        cpu_data: The CPUData object containing current CPU metrics.
            This can be None when no data has been collected yet.
        history_size: Maximum number of historical values to keep for sparkline.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    CPUWidget {
        width: 100%;
        height: auto;
        padding: 0;
    }

    CPUWidget .section-header {
        text-style: bold;
        margin-top: 1;
        padding: 0 1;
    }

    CPUWidget .total-row {
        height: 1;
        margin-bottom: 0;
        padding: 0 1;
    }

    CPUWidget .sparkline-row {
        width: 100%;
        height: 1;
        margin-bottom: 1;
        padding: 0;
    }

    CPUWidget .load-avg-row {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }

    CPUWidget .freq-row {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }

    CPUWidget .cores-container {
        height: auto;
        width: 100%;
        padding: 0 1;
    }
    """

    cpu_data: reactive[CPUData | None] = reactive(None)

    # Default history size - large enough to fill wide terminals
    DEFAULT_HISTORY_SIZE: ClassVar[int] = 200

    # Threshold for considering data significantly changed (percentage points)
    SIGNIFICANT_CHANGE_THRESHOLD: ClassVar[float] = 0.5

    def __init__(
        self,
        cpu_data: CPUData | None = None,
        history_size: int = DEFAULT_HISTORY_SIZE,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the CPU widget.

        Args:
            cpu_data: Initial CPU data to display (optional)
            history_size: Maximum number of historical values to keep (default 60)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        # Initialize instance variables BEFORE setting reactive data
        # to avoid AttributeError in watch_cpu_data
        self._history_size = history_size
        self._usage_history: deque[float] = deque(maxlen=history_size)
        self._last_total_usage: float | None = None  # For change detection
        # Now safe to set reactive data
        self.cpu_data = cpu_data

    @property
    def history_size(self) -> int:
        """Get the maximum history size."""
        return self._history_size

    @property
    def usage_history(self) -> list[float]:
        """Get the current usage history as a list."""
        return list(self._usage_history)

    def compose(self) -> ComposeResult:
        """Compose the CPU widget layout.

        Yields:
            Child widgets for displaying CPU metrics
        """
        if self.cpu_data is None:
            yield Label("Waiting for CPU data...", classes="no-data")
            return

        # Sparkline for CPU usage history (first row, full width, no label)
        yield Sparkline(
            values=list(self._usage_history),
            width=0,  # Auto-width based on container
            min_value=0.0,
            max_value=100.0,
            show_label=False,
            history_size=self._history_size,
            id="cpu-sparkline",
            classes="sparkline-row",
        )

        # Total CPU usage section
        yield Static(self._render_total_usage(), classes="total-row")

        # Load averages
        yield Static(self._render_load_averages(), classes="load-avg-row")

        # Frequency info (if any core has it)
        freq_text = self._render_frequency_info()
        if freq_text:
            yield Static(freq_text, classes="freq-row")

        # Per-core usage section
        if self.cpu_data.cores:
            yield Label("Per-Core Usage:", classes="section-header")
            with Vertical(classes="cores-container"):
                for core in self.cpu_data.cores:
                    yield CoreUsageRow(
                        core_id=core.id,
                        usage_percent=core.usage_percent,
                        freq_mhz=core.freq_mhz,
                        temp_celsius=core.temp_celsius,
                        id=f"core-{core.id}",
                    )

    def _render_total_usage(self) -> RenderableType:
        """Render the total CPU usage line.

        Returns:
            Rich Text with total usage and progress bar
        """
        if self.cpu_data is None:
            return Text("No data")

        usage = self.cpu_data.total_usage_percent
        color = get_usage_color(usage)

        result = Text()
        result.append("Total: ", style="bold")
        result.append(f"{usage:5.1f}%", style=color + " bold")

        # Progress bar
        bar_width = 30
        filled = int((usage / 100.0) * bar_width)
        filled = max(0, min(filled, bar_width))
        empty = bar_width - filled

        result.append(" [", style="dim")
        result.append("=" * filled, style=color)
        result.append(" " * empty, style="dim")
        result.append("]", style="dim")

        result.append(f" ({self.cpu_data.core_count} cores)", style="dim")

        return result

    def _render_load_averages(self) -> RenderableType:
        """Render the load averages line.

        Returns:
            Rich Text with 1/5/15 minute load averages
        """
        if self.cpu_data is None:
            return Text("No data")

        result = Text()
        result.append("Load Avg: ", style="dim")
        result.append(f"{self.cpu_data.load_avg_1min:.2f}", style="white")
        result.append(" / ", style="dim")
        result.append(f"{self.cpu_data.load_avg_5min:.2f}", style="white")
        result.append(" / ", style="dim")
        result.append(f"{self.cpu_data.load_avg_15min:.2f}", style="white")
        result.append(" (1/5/15 min)", style="dim")

        return result

    def _render_frequency_info(self) -> RenderableType | None:
        """Render CPU frequency information if available.

        Returns:
            Rich Text with frequency info, or None if no frequency data
        """
        if self.cpu_data is None or not self.cpu_data.cores:
            return None

        # Get frequencies from cores that have them
        freqs = [c.freq_mhz for c in self.cpu_data.cores if c.freq_mhz is not None]
        if not freqs:
            return None

        avg_freq = sum(freqs) / len(freqs)
        min_freq = min(freqs)
        max_freq = max(freqs)

        result = Text()
        result.append("Frequency: ", style="dim")
        result.append(f"{avg_freq:.0f}", style="white")
        result.append(" MHz avg", style="dim")

        if min_freq != max_freq:
            result.append(f" (min: {min_freq:.0f}, max: {max_freq:.0f})", style="dim")

        return result

    def _has_significant_change(self, new_data: CPUData) -> bool:
        """Check if the new data is significantly different from the last update.

        This helps avoid unnecessary re-renders for tiny fluctuations.

        Args:
            new_data: The new CPU data

        Returns:
            True if the data has changed significantly
        """
        if self._last_total_usage is None:
            return True

        # Check if total usage changed significantly
        usage_diff = abs(new_data.total_usage_percent - self._last_total_usage)
        return usage_diff >= self.SIGNIFICANT_CHANGE_THRESHOLD

    def watch_cpu_data(self, new_data: CPUData | None) -> None:
        """React to cpu_data changes by refreshing the display.

        This also updates the usage history with the new value.
        Uses change detection to avoid unnecessary re-renders.

        Args:
            new_data: The new CPU data
        """
        if new_data is not None:
            self._usage_history.append(new_data.total_usage_percent)

        if self.is_mounted:
            # Try to update sparkline without full recompose if possible
            try:
                sparkline = self.query_one("#cpu-sparkline", Sparkline)
                sparkline.set_values(list(self._usage_history))
            except Exception:
                pass  # Sparkline may not exist yet

            # Only do full recompose if data changed significantly
            if new_data is not None and self._has_significant_change(new_data):
                self._last_total_usage = new_data.total_usage_percent
                self.refresh(recompose=True)
            elif new_data is None:
                self.refresh(recompose=True)

    def update_data(self, data: CPUData) -> None:
        """Update the widget with new CPU data.

        This is a convenience method for updating the display.
        The value is automatically added to the usage history.

        Args:
            data: New CPU data to display
        """
        self.cpu_data = data

    def clear_history(self) -> None:
        """Clear the CPU usage history."""
        self._usage_history.clear()
        if self.is_mounted:
            try:
                sparkline = self.query_one("#cpu-sparkline", Sparkline)
                sparkline.clear()
            except Exception:
                pass  # Sparkline may not exist
