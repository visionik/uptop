"""GPU Widget for uptop TUI.

This module provides a Textual widget for displaying GPU metrics including:
- GPU usage sparkline history
- GPU model, cores, Metal version (Apple Silicon)
- GPU utilization with progress bar (if available)
- Memory pressure (Apple Silicon unified memory)

The widget uses color-coded progress bars:
- Green: 0-50% usage
- Yellow: 50-80% usage
- Red: 80-100% usage
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, ClassVar

from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from uptop.tui.widgets.sparkline import Sparkline

if TYPE_CHECKING:
    from uptop.plugins.gpu import GPUData


# Partial block characters for high-resolution progress bar (8 levels per character)
PROGRESS_CHARS = " ▏▎▍▌▋▊▉█"

# Color thresholds for usage
THRESHOLD_LOW = 50.0  # 0-50% is green
THRESHOLD_MEDIUM = 80.0  # 50-80% is yellow


def get_usage_color(usage_percent: float) -> str:
    """Get the color name for a given usage percentage.

    Args:
        usage_percent: Usage as a percentage (0-100)

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

    Args:
        percent: Progress percentage (0-100)
        width: Total width in characters

    Returns:
        String representation of the progress bar
    """
    if width <= 0:
        return ""

    total_eighths = width * 8
    filled_eighths = int((percent / 100.0) * total_eighths)
    filled_eighths = max(0, min(total_eighths, filled_eighths))

    full_blocks = filled_eighths // 8
    partial_eighths = filled_eighths % 8

    bar = "█" * full_blocks
    if partial_eighths > 0 and full_blocks < width:
        bar += PROGRESS_CHARS[partial_eighths]
    bar += " " * (width - len(bar))

    return bar


def render_empty_bar(width: int) -> str:
    """Render an empty/unavailable progress bar using light shade characters.

    Args:
        width: Total width in characters

    Returns:
        String representation of the empty bar
    """
    return "░" * width


class GPUProgressBar(Static):
    """A progress bar for GPU usage.

    Shows high-resolution progress when usage is available,
    or an empty bar pattern when usage is unavailable.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    GPUProgressBar {
        width: 1fr;
        height: 1;
    }
    """

    percent: reactive[float | None] = reactive(None)

    def __init__(
        self,
        percent: float | None = None,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the GPU progress bar.

        Args:
            percent: Initial percentage (0-100) or None if unavailable
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.percent = percent

    def render(self) -> RenderableType:
        """Render the progress bar."""
        width = self.size.width if self.size.width > 0 else 20

        if self.percent is None:
            # Show empty bar for unavailable data
            bar = render_empty_bar(width)
            return Text(bar, style="dim")

        bar = render_hires_bar(self.percent, width)
        return Text(bar, style=get_usage_color(self.percent))

    def watch_percent(self, new_percent: float | None) -> None:
        """React to percent changes."""
        self.refresh()


class GPUWidget(Widget):
    """Widget for displaying GPU usage and information.

    Displays:
    - Sparkline showing GPU usage history (or memory pressure)
    - GPU model and specs
    - GPU utilization with progress bar
    - Memory pressure

    Attributes:
        gpu_data: The GPUData object containing current GPU metrics
        history_size: Maximum number of historical values for sparkline
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    GPUWidget {
        width: 100%;
        height: auto;
        padding: 0;
    }

    GPUWidget .sparkline-row {
        width: 100%;
        height: 1;
        padding: 0;
    }

    GPUWidget .gpu-info {
        width: 100%;
        height: 1;
        padding: 0;
    }

    GPUWidget .usage-row {
        width: 100%;
        height: 1;
        padding: 0;
        layout: horizontal;
    }

    GPUWidget .usage-label {
        width: 14;
        height: 1;
    }

    GPUWidget .memory-row {
        width: 100%;
        height: 1;
        padding: 0;
    }
    """

    gpu_data: reactive[GPUData | None] = reactive(None)

    DEFAULT_HISTORY_SIZE: ClassVar[int] = 200
    SIGNIFICANT_CHANGE_THRESHOLD: ClassVar[float] = 0.5

    def __init__(
        self,
        gpu_data: GPUData | None = None,
        history_size: int = DEFAULT_HISTORY_SIZE,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the GPU widget.

        Args:
            gpu_data: Optional GPUData to display initially
            history_size: Maximum number of historical values to keep
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._history_size = history_size
        self._usage_history: deque[float] = deque(maxlen=history_size)
        self._last_usage: float | None = None
        self._last_pressure: float | None = None
        self.gpu_data = gpu_data

    @property
    def history_size(self) -> int:
        """Get the maximum history size."""
        return self._history_size

    @property
    def usage_history(self) -> list[float]:
        """Get the current usage history as a list."""
        return list(self._usage_history)

    def compose(self) -> ComposeResult:
        """Compose the GPU widget."""
        # Sparkline for usage history
        yield Sparkline(
            values=list(self._usage_history),
            width=0,
            min_value=0.0,
            max_value=100.0,
            show_label=False,
            history_size=self._history_size,
            id="gpu-sparkline",
            classes="sparkline-row",
        )

        # GPU info line
        yield Label("", id="gpu-info", classes="gpu-info")

        # Usage row with label and progress bar
        with Horizontal(classes="usage-row"):
            yield Label("All: N/A ", id="usage-label", classes="usage-label")
            yield GPUProgressBar(percent=None, id="usage-bar")

        # Memory pressure row
        yield Label("", id="memory-label", classes="memory-row")

    def on_mount(self) -> None:
        """Set up the widget when mounted."""
        if self.gpu_data is not None:
            self._update_display()

    def _update_display(self) -> None:
        """Update the display with current GPU data."""
        if self.gpu_data is None:
            return

        # Update GPU info line
        try:
            info_label = self.query_one("#gpu-info", Label)
            gpu = self.gpu_data.primary_gpu
            if gpu:
                info_parts = [gpu.name]
                if gpu.cores:
                    info_parts.append(f"{gpu.cores} cores")
                if gpu.metal_version:
                    info_parts.append(gpu.metal_version)
                # Format: "Apple M4 Max (40 cores, Metal 4)"
                if len(info_parts) > 1:
                    text = f"{info_parts[0]} ({', '.join(info_parts[1:])})"
                else:
                    text = info_parts[0]
                info_label.update(text)
            else:
                info_label.update("No GPU detected")
        except Exception:
            pass

        # Update usage display
        try:
            usage_label = self.query_one("#usage-label", Label)
            usage_bar = self.query_one("#usage-bar", GPUProgressBar)

            usage = self.gpu_data.gpu_usage_percent
            if usage is not None:
                usage_label.update(f"All: {int(usage):02d}% ")
                usage_bar.percent = usage
            else:
                # Show N/A with hint about sudo
                if self.gpu_data.platform == "apple_silicon":
                    usage_label.update("All: N/A  ")
                else:
                    usage_label.update("All: N/A  ")
                usage_bar.percent = None
        except Exception:
            pass

        # Update memory pressure
        try:
            mem_label = self.query_one("#memory-label", Label)
            pressure = self.gpu_data.memory_pressure_percent
            if pressure is not None:
                color = get_usage_color(pressure)
                mem_label.update(
                    Text.assemble(
                        "Mem Pressure: ",
                        (f"{int(pressure):02d}%", color),
                    )
                )
            else:
                mem_label.update("Mem Pressure: N/A")
        except Exception:
            pass

    def _has_significant_change(self, new_data: GPUData) -> bool:
        """Check if the new data is significantly different.

        Args:
            new_data: The new GPU data

        Returns:
            True if the data has changed significantly
        """
        if self._last_usage is None and self._last_pressure is None:
            return True

        # Check usage change
        new_usage = new_data.gpu_usage_percent
        if new_usage is not None and self._last_usage is not None:
            if abs(new_usage - self._last_usage) >= self.SIGNIFICANT_CHANGE_THRESHOLD:
                return True
        elif new_usage != self._last_usage:  # One is None, other isn't
            return True

        # Check pressure change
        new_pressure = new_data.memory_pressure_percent
        return (
            new_pressure is not None
            and self._last_pressure is not None
            and abs(new_pressure - self._last_pressure) >= self.SIGNIFICANT_CHANGE_THRESHOLD
        )

    def watch_gpu_data(self, new_data: GPUData | None) -> None:
        """React to GPU data changes.

        Args:
            new_data: The new GPUData value
        """
        if new_data is not None:
            # Track either GPU usage or memory pressure for sparkline
            value = new_data.gpu_usage_percent
            if value is None:
                value = new_data.memory_pressure_percent
            if value is not None:
                self._usage_history.append(value)

        if self.is_mounted:
            # Update sparkline
            try:
                sparkline = self.query_one("#gpu-sparkline", Sparkline)
                sparkline.set_values(list(self._usage_history))
            except Exception:
                pass

            # Update display if significant change
            if new_data is not None and self._has_significant_change(new_data):
                self._last_usage = new_data.gpu_usage_percent
                self._last_pressure = new_data.memory_pressure_percent
                self._update_display()
            elif new_data is None:
                self._update_display()

    def update_data(self, data: GPUData) -> None:
        """Update the displayed GPU data.

        Args:
            data: New GPUData to display
        """
        self.gpu_data = data

    def clear_history(self) -> None:
        """Clear the usage history."""
        self._usage_history.clear()
        if self.is_mounted:
            try:
                sparkline = self.query_one("#gpu-sparkline", Sparkline)
                sparkline.clear()
            except Exception:
                pass
