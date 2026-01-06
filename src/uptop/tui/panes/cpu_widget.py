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
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from uptop.models.base import DisplayMode
from uptop.tui.widgets.sparkline import Sparkline

if TYPE_CHECKING:
    from uptop.plugins.cpu import CPUData

# Partial block characters for high-resolution progress bar (8 levels per character)
# From empty to full: space, then ▏▎▍▌▋▊▉█
PROGRESS_CHARS = " ▏▎▍▌▋▊▉█"


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


def render_hires_bar(percent: float, width: int) -> str:
    """Render a high-resolution progress bar using partial block characters.

    Uses 8 sub-character levels for smooth progress display.

    Args:
        percent: Progress percentage (0-100)
        width: Total width in characters

    Returns:
        String representation of the progress bar
    """
    if width <= 0:
        return ""

    # Calculate how many "eighths" are filled
    total_eighths = width * 8
    filled_eighths = int((percent / 100.0) * total_eighths)
    filled_eighths = max(0, min(total_eighths, filled_eighths))

    # Full blocks
    full_blocks = filled_eighths // 8
    # Partial block (0-7 eighths)
    partial_eighths = filled_eighths % 8

    # Build the bar
    bar = "█" * full_blocks
    if partial_eighths > 0 and full_blocks < width:
        bar += PROGRESS_CHARS[partial_eighths]
    # Pad with spaces
    bar += " " * (width - len(bar))

    return bar


class HiResProgressBar(Static):
    """A high-resolution progress bar using partial block characters.

    Provides 8 sub-character levels of precision for smooth progress display.
    """

    DEFAULT_CSS: ClassVar[str] = """
    HiResProgressBar {
        width: 1fr;
        height: 1;
    }
    """

    percent: reactive[float] = reactive(0.0)

    def __init__(
        self,
        percent: float = 0.0,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the high-resolution progress bar.

        Args:
            percent: Initial percentage (0-100)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.percent = percent

    def render(self) -> RenderableType:
        """Render the progress bar."""
        # Use container width for the bar
        width = self.size.width if self.size.width > 0 else 20
        bar = render_hires_bar(self.percent, width)
        return Text(bar, style=get_usage_color(self.percent))

    def watch_percent(self, new_percent: float) -> None:
        """React to percent changes."""
        self.refresh()


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


class CoreUsageRow(Widget):
    """A single row displaying one CPU core's usage.

    Shows: Core ID (3 chars), usage percentage (2 digits), HiResProgressBar.
    Format: "  n: xx% [progressbar...]"
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
        width: auto;
    }

    CoreUsageRow HiResProgressBar {
        width: 1fr;
        height: 1;
        margin-left: 1;
    }
    """

    usage_percent: reactive[float] = reactive(0.0)

    def __init__(
        self,
        core_id: int,
        usage_percent: float,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the core usage row.

        Args:
            core_id: CPU core identifier
            usage_percent: Core usage percentage (0-100)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.core_id = core_id
        self.usage_percent = usage_percent

    def compose(self) -> ComposeResult:
        """Compose the core usage row with label and progress bar."""
        # Format: "  n: xx%" where n is 3-char padded, xx is 2-digit percent
        label_text = f"{self.core_id:3d}: {int(self.usage_percent):02d}%"
        yield Label(label_text, classes="core-label")
        yield HiResProgressBar(percent=self.usage_percent, id=f"core-bar-{self.core_id}")


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
        layout: horizontal;
        width: 100%;
    }

    CPUWidget .total-row .total-label {
        width: auto;
    }

    CPUWidget .total-row HiResProgressBar {
        width: 1fr;
        height: 1;
        margin-left: 1;
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

    CPUWidget .core-row {
        width: 100%;
        height: 1;
        layout: horizontal;
    }

    CPUWidget .core-row CoreUsageRow {
        width: 1fr;
    }
    """

    cpu_data: reactive[CPUData | None] = reactive(None)
    _display_mode: reactive[DisplayMode] = reactive(DisplayMode.MINIMIZED)

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

        match self._display_mode:
            case DisplayMode.MICRO:
                # Ultra-compact: single line with total CPU %
                usage = self.cpu_data.total_usage_percent
                yield Label(f"CPU {int(usage)}%", classes="micro-label")

            case DisplayMode.MINIMIZED:
                # Current implementation - sparkline + total + cores + load/freq
                yield from self._compose_minimized()

            case DisplayMode.MEDIUM:
                # Same as minimized for now (placeholder for future enhancements)
                yield from self._compose_minimized()

            case DisplayMode.MAXIMIZED:
                # Same as minimized for now (placeholder for future enhancements)
                yield from self._compose_minimized()

    def _compose_minimized(self) -> ComposeResult:
        """Compose the minimized layout (also used for MEDIUM and MAXIMIZED).

        Yields:
            Child widgets for minimized display mode
        """
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

        # Total CPU usage section: "All: bb% [HiResProgressBar]"
        usage = self.cpu_data.total_usage_percent
        with Horizontal(classes="total-row", id="total-row"):
            yield Label(
                f"All: {int(usage):02d}%",
                classes="total-label",
            )
            yield HiResProgressBar(
                percent=usage,
                id="total-progress",
            )

        # Per-core usage section (two columns)
        if self.cpu_data.cores:
            cores = self.cpu_data.cores
            with Vertical(classes="cores-container"):
                # Pair cores into rows of 2
                for i in range(0, len(cores), 2):
                    with Horizontal(classes="core-row"):
                        # First core in pair
                        yield CoreUsageRow(
                            core_id=cores[i].id,
                            usage_percent=cores[i].usage_percent,
                            id=f"core-{cores[i].id}",
                        )
                        # Second core in pair (if exists)
                        if i + 1 < len(cores):
                            yield CoreUsageRow(
                                core_id=cores[i + 1].id,
                                usage_percent=cores[i + 1].usage_percent,
                                id=f"core-{cores[i + 1].id}",
                            )

        # Load averages
        yield Static(self._render_load_averages(), classes="load-avg-row")

        # Frequency info (if any core has it)
        freq_text = self._render_frequency_info()
        if freq_text:
            yield Static(freq_text, classes="freq-row")

    def _get_usage_color_class(self, usage_percent: float) -> str:
        """Get CSS class for usage color.

        Args:
            usage_percent: CPU usage percentage

        Returns:
            CSS class name: '', 'medium', or 'high'
        """
        if usage_percent < THRESHOLD_LOW:
            return ""  # Default green
        if usage_percent < THRESHOLD_MEDIUM:
            return "medium"
        return "high"

    def on_mount(self) -> None:
        """Initialize progress bar on mount."""
        if self.cpu_data is not None:
            try:
                progress = self.query_one("#total-progress", HiResProgressBar)
                progress.percent = self.cpu_data.total_usage_percent
            except Exception:
                pass

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

            # Update progress bar and label
            if new_data is not None:
                try:
                    progress = self.query_one("#total-progress", HiResProgressBar)
                    progress.percent = new_data.total_usage_percent

                    # Update label
                    label = self.query_one(".total-label", Label)
                    label.update(f"All: {int(new_data.total_usage_percent):02d}%")
                except Exception:
                    pass

            # Only do full recompose if data changed significantly
            if new_data is not None and self._has_significant_change(new_data):
                self._last_total_usage = new_data.total_usage_percent
                self.refresh(recompose=True)
            elif new_data is None:
                self.refresh(recompose=True)

    def update_data(self, data: CPUData, mode: DisplayMode | None = None) -> None:
        """Update the widget with new CPU data.

        This is a convenience method for updating the display.
        The value is automatically added to the usage history.

        Args:
            data: New CPU data to display
            mode: Optional display mode to switch to
        """
        if mode is not None and mode != self._display_mode:
            self._display_mode = mode
            self.recompose()
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
