"""Disk Widget for uptop TUI.

This module provides a Textual widget for displaying disk/mount information:
- Disk I/O statistics table (read/write bytes/sec, IOPS)
- Per-mount filesystem usage with progress bars
- Color-coded usage indicators (green/yellow/red)
- Human-readable size formatting
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Label, ProgressBar, Static

from uptop.models.base import DisplayMode

if TYPE_CHECKING:
    from uptop.plugins.disk import DiskData, PartitionInfo


def format_bytes(num_bytes: int | float) -> str:
    """Format bytes value with appropriate unit (KB or larger).

    Matches network widget formatting style:
    - Always converts to at least KB (never shows plain bytes)
    - No space between number and unit (e.g., "1.2GB" not "1.2 GB")

    Args:
        num_bytes: Number of bytes

    Returns:
        Formatted string like "1.2GB" or "456KB"
    """
    if num_bytes < 0:
        num_bytes = 0

    # Always convert to at least KB
    kb_val = num_bytes / 1024.0

    for unit in ["KB", "MB", "GB", "TB"]:
        if abs(kb_val) < 1024.0:
            return f"{kb_val:.1f}{unit}"
        kb_val /= 1024.0
    return f"{kb_val:.1f}PB"


def get_usage_color(percent: float) -> str:
    """Get color class based on usage percentage.

    Args:
        percent: Usage percentage (0-100)

    Returns:
        Color class name: "usage-low", "usage-medium", or "usage-high"
    """
    if percent < 70.0:
        return "usage-low"
    if percent < 90.0:
        return "usage-medium"
    return "usage-high"


class PartitionDisplay(Static):
    """Display widget for a single partition/mount point.

    Shows mountpoint, usage bar, and size information.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    PartitionDisplay {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    PartitionDisplay .mount-label {
        width: 100%;
        height: 1;
    }

    PartitionDisplay .usage-bar {
        width: 100%;
        height: 1;
    }

    PartitionDisplay .usage-bar Bar {
        width: 1fr;
    }

    PartitionDisplay .usage-bar.usage-low Bar > .bar--bar {
        background: $success;
    }

    PartitionDisplay .usage-bar.usage-medium Bar > .bar--bar {
        background: $warning;
    }

    PartitionDisplay .usage-bar.usage-high Bar > .bar--bar {
        background: $error;
    }

    PartitionDisplay .size-info {
        width: 100%;
        height: 1;
        text-align: right;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        partition: PartitionInfo,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the partition display.

        Args:
            partition: Partition information to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._partition = partition

    def compose(self) -> ComposeResult:
        """Compose the partition display."""
        partition = self._partition

        # Mount point and filesystem type
        yield Label(
            f"{partition.mountpoint} ({partition.fstype})",
            classes="mount-label",
        )

        # Usage progress bar with color coding
        usage_color = get_usage_color(partition.percent)
        progress_bar = ProgressBar(
            total=100,
            show_eta=False,
            show_percentage=True,
            classes=f"usage-bar {usage_color}",
        )
        progress_bar.update(progress=partition.percent)
        yield progress_bar

        # Size information
        used = format_bytes(partition.used_bytes)
        total = format_bytes(partition.total_bytes)
        free = format_bytes(partition.free_bytes)
        yield Label(
            f"{used} / {total} ({free} free)",
            classes="size-info",
        )


def format_iops(iops: float) -> str:
    """Format IOPS value with appropriate suffix.

    Args:
        iops: IOPS value

    Returns:
        Formatted string (e.g., "1.2K", "500")
    """
    if iops < 1000:
        return str(int(iops))
    if iops < 1_000_000:
        return f"{iops / 1000:.1f}K"
    return f"{iops / 1_000_000:.1f}M"


class DiskWidget(Widget):
    """Main disk widget displaying I/O stats table and filesystem usage.

    Displays:
    - Disk I/O statistics table (similar to network widget)
    - Per-mount filesystem usage with progress bars
    - Color-coded usage indicators (green < 70%, yellow 70-90%, red > 90%)

    Attributes:
        data: The current DiskData to display
        prev_data: Previous DiskData for rate calculations
        refresh_interval: Expected refresh interval in seconds
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    DiskWidget {
        width: 100%;
        height: 100%;
        padding: 0;
    }

    DiskWidget .no-data {
        width: 100%;
        height: 3;
        content-align: center middle;
        color: $text-muted;
    }

    DiskWidget #io-table {
        width: 100%;
        height: auto;
        max-height: 50%;
        scrollbar-size: 1 1;
    }

    DiskWidget .partitions-container {
        width: 100%;
        height: auto;
        padding-top: 1;
    }
    """

    # Reactive property for data - triggers re-render on change
    data: reactive[DiskData | None] = reactive(None)
    prev_data: reactive[DiskData | None] = reactive(None)
    refresh_interval: reactive[float] = reactive(5.0)
    _display_mode: reactive[DisplayMode] = reactive(DisplayMode.MINIMIZED)

    def __init__(
        self,
        data: DiskData | None = None,
        refresh_interval: float = 5.0,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the disk widget.

        Args:
            data: Initial DiskData to display
            refresh_interval: Expected refresh interval in seconds
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.data = data
        self.prev_data = None
        self.refresh_interval = refresh_interval
        self._io_rates: dict[str, dict[str, float]] = {}

    def compose(self) -> ComposeResult:
        """Compose the disk widget."""
        match self._display_mode:
            case DisplayMode.MICRO:
                # Ultra-compact: single line with primary disk usage %
                if self.data and self.data.partitions:
                    # Find root partition or first partition
                    root = next((p for p in self.data.partitions if p.mountpoint == "/"), None)
                    if root:
                        yield Label(f"Disk {int(root.percent)}%", classes="micro-label")
                    else:
                        p = self.data.partitions[0]
                        yield Label(f"Disk {int(p.percent)}%", classes="micro-label")
                else:
                    yield Label("Disk --", classes="micro-label")

            case DisplayMode.MINIMIZED:
                # Current implementation - I/O table + partitions
                yield from self._compose_minimized()

            case DisplayMode.MEDIUM:
                # Same as minimized for now
                yield from self._compose_minimized()

            case DisplayMode.MAXIMIZED:
                # Same as minimized for now
                yield from self._compose_minimized()

    def _compose_minimized(self) -> ComposeResult:
        """Compose the minimized view with I/O table and partitions."""
        # I/O stats table (first)
        yield DataTable(id="io-table")

        # Partitions container (second)
        yield Vertical(id="partitions-container", classes="partitions-container")

    def on_mount(self) -> None:
        """Set up the data table when the widget is mounted."""
        table = self.query_one("#io-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns matching network widget style
        table.add_column("Disk", key="device", width=10)
        table.add_column("Read/s", key="read_rate", width=9)
        table.add_column("Write/s", key="write_rate", width=9)
        table.add_column("R IOPS", key="read_iops", width=7)
        table.add_column("W IOPS", key="write_iops", width=7)
        table.add_column("Read Tot", key="read_total", width=9)
        table.add_column("Write Tot", key="write_total", width=9)

        # Populate with initial data if available
        if self.data is not None:
            self._update_io_table()
            self._update_partitions()

    def _calculate_rates(self) -> dict[str, dict[str, float]]:
        """Calculate I/O rates from current and previous stats.

        Returns:
            Dictionary mapping device names to their rates
        """
        rates: dict[str, dict[str, float]] = {}

        if not self.data or not self.data.io_stats:
            return rates

        if not self.prev_data or not self.prev_data.io_stats:
            # No previous stats, can't calculate rates
            return rates

        # Build lookup for previous stats
        prev_lookup = {stat.device: stat for stat in self.prev_data.io_stats}

        for stat in self.data.io_stats:
            prev = prev_lookup.get(stat.device)
            if prev:
                interval = self.refresh_interval
                # Calculate byte rates
                read_bytes_rate = max(0, (stat.read_bytes - prev.read_bytes)) / interval
                write_bytes_rate = max(0, (stat.write_bytes - prev.write_bytes)) / interval

                # Calculate IOPS
                read_iops = max(0, (stat.read_count - prev.read_count)) / interval
                write_iops = max(0, (stat.write_count - prev.write_count)) / interval

                rates[stat.device] = {
                    "read_bytes_rate": read_bytes_rate,
                    "write_bytes_rate": write_bytes_rate,
                    "read_iops": read_iops,
                    "write_iops": write_iops,
                }

        return rates

    def _has_activity(self, device: str) -> bool:
        """Check if a disk has recent I/O activity.

        Args:
            device: Device name to check

        Returns:
            True if the device has non-zero rates
        """
        rates = self._io_rates.get(device, {})
        return (
            rates.get("read_bytes_rate", 0) > 0
            or rates.get("write_bytes_rate", 0) > 0
        )

    def _update_io_table(self) -> None:
        """Update the I/O stats table with current data."""
        if self.data is None or not self.data.io_stats:
            return

        try:
            table = self.query_one("#io-table", DataTable)
        except Exception:
            return  # Widget not ready

        # Calculate rates
        self._io_rates = self._calculate_rates()

        # Save scroll position and cursor before clearing
        saved_scroll_y = table.scroll_y
        saved_cursor_row = table.cursor_row

        # Clear existing rows
        table.clear()

        # Sort disks: active disks first, then by name
        sorted_stats = sorted(
            self.data.io_stats,
            key=lambda x: (not self._has_activity(x.device), x.device),
        )

        # Add rows for each disk
        for stat in sorted_stats:
            rates = self._io_rates.get(stat.device, {})

            read_rate = format_bytes(rates.get("read_bytes_rate", 0))
            write_rate = format_bytes(rates.get("write_bytes_rate", 0))
            read_iops = format_iops(rates.get("read_iops", 0))
            write_iops = format_iops(rates.get("write_iops", 0))
            read_total = format_bytes(stat.read_bytes)
            write_total = format_bytes(stat.write_bytes)

            table.add_row(
                stat.device,
                read_rate.rjust(9),
                write_rate.rjust(9),
                read_iops.rjust(7),
                write_iops.rjust(7),
                read_total.rjust(9),
                write_total.rjust(9),
                key=stat.device,
            )

        # Restore scroll position and cursor after layout completes
        row_count = table.row_count
        if row_count > 0 and (saved_cursor_row is not None or saved_scroll_y > 0):
            def restore_scroll() -> None:
                """Restore scroll position after layout."""
                if saved_cursor_row is not None and table.row_count > 0:
                    target_row = min(saved_cursor_row, table.row_count - 1)
                    table.move_cursor(row=target_row)
                if saved_scroll_y > 0:
                    table.scroll_y = saved_scroll_y

            self.call_after_refresh(restore_scroll)

    def _update_partitions(self) -> None:
        """Update the partitions display."""
        if self.data is None:
            return

        try:
            container = self.query_one("#partitions-container", Vertical)
        except Exception:
            return  # Widget not ready

        # Clear and repopulate partitions
        container.remove_children()
        for partition in self.data.partitions:
            container.mount(PartitionDisplay(partition))

    def update_data(self, new_data: DiskData, mode: DisplayMode | None = None) -> None:
        """Update the widget with new disk data.

        Args:
            new_data: New DiskData to display
            mode: Optional display mode to switch to
        """
        if mode is not None and mode != self._display_mode:
            self._display_mode = mode
            self.recompose()
        # Store current data as previous for rate calculations
        self.prev_data = self.data
        self.data = new_data

        if self.is_mounted:
            self._update_io_table()
            self._update_partitions()

    def watch_data(self, new_data: DiskData | None) -> None:
        """React to data changes.

        Args:
            new_data: The new DiskData value
        """
        if self.is_mounted and new_data is not None:
            self._update_io_table()
            self._update_partitions()
