"""Memory Widget for uptop TUI.

This module provides a widget for displaying memory (RAM and Swap) usage:
- RAM usage sparkline showing history
- Table format with P-MEM (Physical) and V-MEM (Virtual/Swap) columns
- P-MAX and V-MAX columns tracking maximum values seen
- Rows: Total, Used, Free, Available, Active, Inactive
"""

from collections import deque
from dataclasses import dataclass
from typing import ClassVar

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Label

from uptop.models.base import DisplayMode
from uptop.plugins.memory import MemoryData
from uptop.tui.widgets.sparkline import Sparkline


@dataclass
class MaxTracker:
    """Track maximum values for memory metrics."""

    # Physical memory max values
    p_used: int = 0
    p_free: int = 0
    p_available: int = 0
    p_active: int = 0
    p_inactive: int = 0

    # Virtual (swap) memory max values
    v_used: int = 0
    v_free: int = 0

    def update(self, data: MemoryData) -> None:
        """Update max values from new data."""
        vm = data.virtual
        swap = data.swap

        self.p_used = max(self.p_used, vm.used_bytes)
        self.p_free = max(self.p_free, vm.free_bytes)
        self.p_available = max(self.p_available, vm.available_bytes)
        if vm.active_bytes is not None:
            self.p_active = max(self.p_active, vm.active_bytes)
        if vm.inactive_bytes is not None:
            self.p_inactive = max(self.p_inactive, vm.inactive_bytes)

        self.v_used = max(self.v_used, swap.used_bytes)
        self.v_free = max(self.v_free, swap.free_bytes)


def format_bytes(bytes_val: int | float) -> str:
    """Format bytes value with appropriate unit (KB or larger).

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string like "1.2GB" or "456KB" (no space, never plain bytes)
    """
    # Always convert to at least KB
    kb_val = bytes_val / 1024.0

    for unit in ["KB", "MB", "GB", "TB"]:
        if abs(kb_val) < 1024.0:
            return f"{kb_val:.1f}{unit}"
        kb_val /= 1024.0
    return f"{kb_val:.1f}PB"


class MemoryWidget(Widget):
    """Widget for displaying RAM and Swap memory usage in table format.

    Displays:
    - RAM usage sparkline showing history
    - Table with Physical and Virtual columns
    - Rows: Total, Used, Free, Available

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

    MemoryWidget .sparkline-row {
        width: 100%;
        height: 1;
        padding: 0;
    }

    MemoryWidget #memory-table {
        width: 100%;
        height: auto;
        scrollbar-size: 0 0;
    }

    MemoryWidget .micro-label {
        width: 100%;
        height: 1;
    }
    """

    data: reactive[MemoryData | None] = reactive(None)
    _display_mode: reactive[DisplayMode] = reactive(DisplayMode.MINIMIZED)

    # Default history size - large enough to fill wide terminals
    DEFAULT_HISTORY_SIZE: ClassVar[int] = 200

    # Threshold for considering data significantly changed (percentage points)
    SIGNIFICANT_CHANGE_THRESHOLD: ClassVar[float] = 0.5

    def __init__(
        self,
        data: MemoryData | None = None,
        history_size: int = DEFAULT_HISTORY_SIZE,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the memory widget.

        Args:
            data: Optional MemoryData to display initially
            history_size: Maximum number of historical values to keep (default 60)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._history_size = history_size
        self._usage_history: deque[float] = deque(maxlen=history_size)
        self._last_ram_percent: float | None = None
        self._last_swap_percent: float | None = None
        self._max_tracker = MaxTracker()
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
        """Compose the memory widget based on display mode."""
        match self._display_mode:
            case DisplayMode.MICRO:
                # Ultra-compact: single line with RAM usage %
                if self.data:
                    pct = self.data.virtual.percent
                    yield Label(f"RAM {int(pct)}%", classes="micro-label")
                else:
                    yield Label("RAM --", classes="micro-label")

            case DisplayMode.MINIMIZED:
                # Current implementation - sparkline + table
                yield from self._compose_minimized()

            case DisplayMode.MEDIUM:
                # Same as minimized for now
                yield from self._compose_minimized()

            case DisplayMode.MAXIMIZED:
                # Same as minimized for now
                yield from self._compose_minimized()

    def _compose_minimized(self) -> ComposeResult:
        """Compose the minimized view with sparkline and table."""
        # Sparkline for RAM usage history
        yield Sparkline(
            values=list(self._usage_history),
            width=0,
            min_value=0.0,
            max_value=100.0,
            show_label=False,
            history_size=self._history_size,
            id="memory-sparkline",
            classes="sparkline-row",
        )

        # Table for detailed stats
        yield DataTable(id="memory-table")

    def on_mount(self) -> None:
        """Set up the data table when mounted."""
        table = self.query_one("#memory-table", DataTable)
        table.show_cursor = False
        table.zebra_stripes = False

        # Add columns: Metric, P-MEM, P-MAX, V-MEM, V-MAX
        table.add_column("", key="metric", width=10)
        table.add_column("P-MEM", key="p_mem", width=10)
        table.add_column("P-MAX", key="p_max", width=10)
        table.add_column("V-MEM", key="v_mem", width=10)
        table.add_column("V-MAX", key="v_max", width=10)

        # Populate table
        if self.data is not None:
            self._update_table()

    def _update_table(self) -> None:
        """Update the table with current memory data."""
        if self.data is None:
            return

        try:
            table = self.query_one("#memory-table", DataTable)
        except Exception:
            return

        table.clear()

        vm = self.data.virtual
        swap = self.data.swap
        mx = self._max_tracker

        # Helper to format and right-justify
        def fmt(val: int | float | None, show: bool = True) -> str:
            if val is None or not show:
                return "".rjust(10)
            return format_bytes(val).rjust(10)

        has_swap = swap.total_bytes > 0
        blank = "".rjust(10)

        # Total row - max is same as current (doesn't change)
        table.add_row(
            "Total",
            fmt(vm.total_bytes), fmt(vm.total_bytes),
            fmt(swap.total_bytes, has_swap), fmt(swap.total_bytes, has_swap),
            key="total"
        )

        # Used row
        table.add_row(
            "Used",
            fmt(vm.used_bytes), fmt(mx.p_used),
            fmt(swap.used_bytes, has_swap), fmt(mx.v_used, has_swap),
            key="used"
        )

        # Free row
        table.add_row(
            "Free",
            fmt(vm.free_bytes), fmt(mx.p_free),
            fmt(swap.free_bytes, has_swap), fmt(mx.v_free, has_swap),
            key="free"
        )

        # Available row (swap doesn't have available)
        table.add_row(
            "Available",
            fmt(vm.available_bytes), fmt(mx.p_available),
            blank, blank,
            key="available"
        )

        # Active row (macOS/Linux only, swap doesn't have)
        if vm.active_bytes is not None:
            table.add_row(
                "Active",
                fmt(vm.active_bytes), fmt(mx.p_active),
                blank, blank,
                key="active"
            )

        # Inactive row (macOS/Linux only, swap doesn't have)
        if vm.inactive_bytes is not None:
            table.add_row(
                "Inactive",
                fmt(vm.inactive_bytes), fmt(mx.p_inactive),
                blank, blank,
                key="inactive"
            )

    def _has_significant_change(self, new_data: MemoryData) -> bool:
        """Check if the new data is significantly different from the last update.

        Args:
            new_data: The new memory data

        Returns:
            True if the data has changed significantly
        """
        if self._last_ram_percent is None:
            return True

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

        Args:
            new_data: The new MemoryData value
        """
        if new_data is not None:
            self._usage_history.append(new_data.virtual.percent)
            self._max_tracker.update(new_data)

        if self.is_mounted:
            # Update sparkline
            try:
                sparkline = self.query_one("#memory-sparkline", Sparkline)
                sparkline.set_values(list(self._usage_history))
            except Exception:
                pass

            # Update table if significant change
            if new_data is not None and self._has_significant_change(new_data):
                self._last_ram_percent = new_data.virtual.percent
                self._last_swap_percent = new_data.swap.percent
                self._update_table()
            elif new_data is None:
                self._update_table()

    def update_data(self, data: MemoryData, mode: DisplayMode | None = None) -> None:
        """Update the displayed memory data.

        Args:
            data: New MemoryData to display
            mode: Optional display mode to switch to
        """
        if mode is not None and mode != self._display_mode:
            self._display_mode = mode
            self.recompose()
        self.data = data

    def clear_history(self) -> None:
        """Clear the memory usage history."""
        self._usage_history.clear()
        if self.is_mounted:
            try:
                sparkline = self.query_one("#memory-sparkline", Sparkline)
                sparkline.clear()
            except Exception:
                pass
