"""Memory Widget for uptop TUI.

This module provides a widget for displaying memory (RAM and Swap) usage:
- RAM usage bar with percentage and human-readable sizes
- RAM usage sparkline showing history
- RAM details: total, used, free, available, cached, buffers
- Swap usage bar with percentage
- Swap details: total, used, free
- Color coding: green (0-60%), yellow (60-85%), red (85-100%)
- Smooth animated progress bar updates
"""

from collections import deque
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static

from uptop.plugins.memory import MemoryData
from uptop.tui.widgets.sparkline import Sparkline

# Animation duration for smooth progress bar updates (in seconds)
PROGRESS_ANIMATION_DURATION = 0.2


def format_bytes(num_bytes: int) -> str:
    """Format bytes to human-readable string with appropriate unit.

    Uses binary units (1024 base) and auto-scales to the appropriate unit.

    Args:
        num_bytes: Number of bytes to format

    Returns:
        Human-readable string (e.g., "16.0 GB", "512.5 MB")
    """
    if num_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(num_bytes)

    for unit in units:
        if abs(value) < 1024.0:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0

    return f"{value:.1f} EB"


def get_usage_color(percent: float) -> str:
    """Get color class based on usage percentage.

    Args:
        percent: Usage percentage (0-100)

    Returns:
        Color class name: "low" (green), "medium" (yellow), or "high" (red)
    """
    if percent < 60:
        return "low"
    if percent < 85:
        return "medium"
    return "high"


class MemoryBar(Static):
    """A progress bar widget for memory usage with label and percentage.

    Displays a labeled progress bar with usage percentage and color coding.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    MemoryBar {
        width: 100%;
        height: 2;
        layout: horizontal;
        padding: 0;
    }

    MemoryBar .bar-label {
        width: 6;
        text-align: left;
        padding-right: 1;
    }

    MemoryBar .bar-container {
        width: 1fr;
        height: 1;
    }

    MemoryBar ProgressBar {
        width: 100%;
        height: 1;
    }

    MemoryBar ProgressBar Bar {
        width: 100%;
    }

    MemoryBar ProgressBar Bar > .bar--indeterminate {
        color: $primary;
    }

    MemoryBar ProgressBar Bar > .bar--bar {
        color: $success;
    }

    MemoryBar.medium ProgressBar Bar > .bar--bar {
        color: $warning;
    }

    MemoryBar.high ProgressBar Bar > .bar--bar {
        color: $error;
    }

    MemoryBar .bar-percent {
        width: 7;
        text-align: right;
        padding-left: 1;
    }
    """

    label: reactive[str] = reactive("MEM")
    percent: reactive[float] = reactive(0.0)

    def __init__(
        self,
        label: str = "MEM",
        percent: float = 0.0,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the memory bar.

        Args:
            label: Label to display (e.g., "RAM", "Swap")
            percent: Usage percentage (0-100)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.label = label
        self.percent = percent
        self._update_color_class()

    def compose(self) -> ComposeResult:
        """Compose the memory bar with label, progress bar, and percentage."""
        yield Label(self.label, classes="bar-label")
        yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress")
        yield Label(f"{self.percent:5.1f}%", classes="bar-percent")

    def on_mount(self) -> None:
        """Initialize progress bar value on mount."""
        progress = self.query_one("#progress", ProgressBar)
        progress.update(progress=self.percent)

    def _update_color_class(self) -> None:
        """Update CSS class based on usage percentage."""
        self.remove_class("low", "medium", "high")
        self.add_class(get_usage_color(self.percent))

    def watch_percent(self, new_percent: float) -> None:
        """React to percent changes with smooth animation.

        Uses Textual's animation system to smoothly transition
        the progress bar value instead of jumping.

        Args:
            new_percent: The new percentage value
        """
        self._update_color_class()
        if self.is_mounted:
            try:
                progress = self.query_one("#progress", ProgressBar)
                # Use animated update for smooth transitions
                # Note: ProgressBar.update() sets progress directly,
                # we animate by updating in steps
                progress.update(progress=new_percent)
                percent_label = self.query_one(".bar-percent", Label)
                percent_label.update(f"{new_percent:5.1f}%")
            except Exception:
                pass  # Widget may not be composed yet

    def watch_label(self, new_label: str) -> None:
        """React to label changes.

        Args:
            new_label: The new label value
        """
        if self.is_mounted:
            try:
                label_widget = self.query_one(".bar-label", Label)
                label_widget.update(new_label)
            except Exception:
                pass  # Widget may not be composed yet


class MemoryDetails(Static):
    """Widget displaying detailed memory statistics.

    Shows human-readable memory values in a compact format.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    MemoryDetails {
        width: 100%;
        height: auto;
        padding: 0 1;
    }

    MemoryDetails .detail-row {
        width: 100%;
        height: 1;
    }

    MemoryDetails .detail-label {
        width: 12;
        text-align: left;
        color: $text-muted;
    }

    MemoryDetails .detail-value {
        width: 1fr;
        text-align: left;
    }
    """

    def __init__(
        self,
        details: list[tuple[str, str]],
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the memory details.

        Args:
            details: List of (label, value) tuples to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._details = details

    def compose(self) -> ComposeResult:
        """Compose the details as label-value pairs."""
        for label, value in self._details:
            with Static(classes="detail-row"):
                yield Label(f"{label}:", classes="detail-label")
                yield Label(value, classes="detail-value")

    def update_details(self, details: list[tuple[str, str]]) -> None:
        """Update the displayed details.

        Args:
            details: New list of (label, value) tuples
        """
        self._details = details
        if self.is_mounted:
            self.refresh(recompose=True)


class MemoryWidget(Widget):
    """Widget for displaying RAM and Swap memory usage.

    Displays:
    - RAM usage bar with percentage
    - RAM usage sparkline showing history
    - RAM details: total, used, free, available, cached, buffers
    - Swap usage bar with percentage
    - Swap details: total, used, free

    Color coding based on usage:
    - Green (low): 0-60%
    - Yellow (medium): 60-85%
    - Red (high): 85-100%

    Attributes:
        data: The MemoryData object containing current memory metrics.
        history_size: Maximum number of historical values to keep for sparkline.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    MemoryWidget {
        width: 100%;
        height: auto;
        padding: 0;
    }

    MemoryWidget .section {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    MemoryWidget .section:last-child {
        margin-bottom: 0;
    }

    MemoryWidget .section-title {
        width: 100%;
        height: 1;
        text-style: bold;
        padding: 0 1;
        color: $text;
    }

    MemoryWidget .sparkline-row {
        height: 1;
        padding: 0 1;
    }
    """

    data: reactive[MemoryData | None] = reactive(None)

    # Default history size (60 samples = 1 minute at 1 sample/second)
    DEFAULT_HISTORY_SIZE: ClassVar[int] = 60

    # Threshold for considering data significantly changed (percentage points)
    SIGNIFICANT_CHANGE_THRESHOLD: ClassVar[float] = 0.5

    def __init__(
        self,
        data: MemoryData | None = None,
        history_size: int = DEFAULT_HISTORY_SIZE,
        sparkline_width: int = 30,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the memory widget.

        Args:
            data: Optional MemoryData to display initially
            history_size: Maximum number of historical values to keep (default 60)
            sparkline_width: Width of the sparkline in characters (default 30)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        # Initialize instance variables BEFORE setting reactive data
        # to avoid AttributeError in watch_data
        self._history_size = history_size
        self._sparkline_width = sparkline_width
        self._usage_history: deque[float] = deque(maxlen=history_size)
        self._last_ram_percent: float | None = None  # For change detection
        self._last_swap_percent: float | None = None
        # Now safe to set reactive data
        self.data = data

    @property
    def history_size(self) -> int:
        """Get the maximum history size."""
        return self._history_size

    @property
    def usage_history(self) -> list[float]:
        """Get the current usage history as a list."""
        return list(self._usage_history)

    def compose(self) -> ComposeResult:
        """Compose the memory widget with RAM and Swap sections."""
        if self.data is None:
            yield Label("No memory data available", id="no-data")
            return

        # RAM Section
        with Vertical(classes="section", id="ram-section"):
            yield MemoryBar(
                label="RAM",
                percent=self.data.virtual.percent,
                id="ram-bar",
            )
            # Sparkline for RAM usage history
            yield Sparkline(
                values=list(self._usage_history),
                width=self._sparkline_width,
                min_value=0.0,
                max_value=100.0,
                show_label=True,
                label="History",
                history_size=self._history_size,
                id="memory-sparkline",
                classes="sparkline-row",
            )
            yield MemoryDetails(
                details=self._get_ram_details(),
                id="ram-details",
            )

        # Swap Section
        with Vertical(classes="section", id="swap-section"):
            yield MemoryBar(
                label="Swap",
                percent=self.data.swap.percent,
                id="swap-bar",
            )
            yield MemoryDetails(
                details=self._get_swap_details(),
                id="swap-details",
            )

    def _get_ram_details(self) -> list[tuple[str, str]]:
        """Get RAM details as label-value pairs.

        Returns:
            List of (label, value) tuples for RAM metrics
        """
        if self.data is None:
            return []

        vm = self.data.virtual
        details = [
            ("Total", format_bytes(vm.total_bytes)),
            ("Used", format_bytes(vm.used_bytes)),
            ("Free", format_bytes(vm.free_bytes)),
            ("Available", format_bytes(vm.available_bytes)),
        ]

        if vm.cached_bytes is not None:
            details.append(("Cached", format_bytes(vm.cached_bytes)))

        if vm.buffers_bytes is not None:
            details.append(("Buffers", format_bytes(vm.buffers_bytes)))

        return details

    def _get_swap_details(self) -> list[tuple[str, str]]:
        """Get Swap details as label-value pairs.

        Returns:
            List of (label, value) tuples for Swap metrics
        """
        if self.data is None:
            return []

        swap = self.data.swap

        if swap.total_bytes == 0:
            return [("Status", "Not configured")]

        return [
            ("Total", format_bytes(swap.total_bytes)),
            ("Used", format_bytes(swap.used_bytes)),
            ("Free", format_bytes(swap.free_bytes)),
        ]

    def _has_significant_change(self, new_data: MemoryData) -> bool:
        """Check if the new data is significantly different from the last update.

        This helps avoid unnecessary re-renders for tiny fluctuations.

        Args:
            new_data: The new memory data

        Returns:
            True if the data has changed significantly
        """
        if self._last_ram_percent is None:
            return True

        # Check if RAM or swap usage changed significantly
        ram_diff = abs(new_data.virtual.percent - self._last_ram_percent)
        swap_diff = 0.0
        if self._last_swap_percent is not None:
            swap_diff = abs(new_data.swap.percent - self._last_swap_percent)

        return (
            ram_diff >= self.SIGNIFICANT_CHANGE_THRESHOLD
            or swap_diff >= self.SIGNIFICANT_CHANGE_THRESHOLD
        )

    def watch_data(self, new_data: MemoryData | None) -> None:
        """React to data changes.

        This also updates the usage history with the new value.
        Uses change detection to avoid unnecessary re-renders.

        Args:
            new_data: The new MemoryData value
        """
        if new_data is not None:
            self._usage_history.append(new_data.virtual.percent)

        if self.is_mounted:
            # Try to update sparkline without full recompose if possible
            try:
                sparkline = self.query_one("#memory-sparkline", Sparkline)
                sparkline.set_values(list(self._usage_history))
            except Exception:
                pass  # Sparkline may not exist yet

            # Only do full recompose if data changed significantly
            if new_data is not None and self._has_significant_change(new_data):
                self._last_ram_percent = new_data.virtual.percent
                self._last_swap_percent = new_data.swap.percent
                self.refresh(recompose=True)
            elif new_data is None:
                self.refresh(recompose=True)

    def update_data(self, data: MemoryData) -> None:
        """Update the displayed memory data.

        This is a convenience method for updating the display.
        The value is automatically added to the usage history.

        Args:
            data: New MemoryData to display
        """
        self.data = data

    def clear_history(self) -> None:
        """Clear the memory usage history."""
        self._usage_history.clear()
        if self.is_mounted:
            try:
                sparkline = self.query_one("#memory-sparkline", Sparkline)
                sparkline.clear()
            except Exception:
                pass  # Sparkline may not exist
