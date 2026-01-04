"""Disk Widget for uptop TUI.

This module provides a Textual widget for displaying disk/mount information:
- Per-mount filesystem usage with progress bars
- Color-coded usage indicators (green/yellow/red)
- Disk I/O statistics (read/write bytes/sec, IOPS)
- Human-readable size formatting
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static

if TYPE_CHECKING:
    from uptop.plugins.disk import DiskData, DiskIOStats, PartitionInfo


def format_bytes(num_bytes: int | float) -> str:
    """Format bytes to human-readable string.

    Args:
        num_bytes: Number of bytes

    Returns:
        Human-readable string (e.g., "1.5 GB", "256 MB")
    """
    if num_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(num_bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def format_rate(bytes_per_sec: float) -> str:
    """Format bytes per second to human-readable rate string.

    Args:
        bytes_per_sec: Bytes per second

    Returns:
        Human-readable rate string (e.g., "1.5 MB/s")
    """
    return f"{format_bytes(bytes_per_sec)}/s"


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


class IOStatsDisplay(Static):
    """Display widget for disk I/O statistics.

    Shows read/write rates and IOPS in a compact format.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    IOStatsDisplay {
        width: 100%;
        height: auto;
        padding: 0 1;
        border-top: solid $primary-darken-2;
        margin-top: 1;
    }

    IOStatsDisplay .io-header {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $text;
    }

    IOStatsDisplay .io-stats-line {
        width: 100%;
        height: 1;
        color: $text-muted;
    }

    IOStatsDisplay .read-stats {
        color: $success;
    }

    IOStatsDisplay .write-stats {
        color: $warning;
    }
    """

    def __init__(
        self,
        io_stats: list[DiskIOStats],
        prev_io_stats: list[DiskIOStats] | None = None,
        interval: float = 1.0,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the I/O stats display.

        Args:
            io_stats: Current I/O statistics
            prev_io_stats: Previous I/O statistics for rate calculation
            interval: Time interval in seconds between samples
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._io_stats = io_stats
        self._prev_io_stats = prev_io_stats
        self._interval = interval

    def _calculate_rates(
        self,
    ) -> dict[str, dict[str, float]]:
        """Calculate I/O rates from current and previous stats.

        Returns:
            Dictionary mapping device names to their rates
        """
        rates: dict[str, dict[str, float]] = {}

        if not self._prev_io_stats:
            # No previous stats, can't calculate rates
            return rates

        # Build lookup for previous stats
        prev_lookup = {stat.device: stat for stat in self._prev_io_stats}

        for stat in self._io_stats:
            prev = prev_lookup.get(stat.device)
            if prev:
                # Calculate byte rates
                read_bytes_rate = max(0, (stat.read_bytes - prev.read_bytes)) / self._interval
                write_bytes_rate = max(0, (stat.write_bytes - prev.write_bytes)) / self._interval

                # Calculate IOPS
                read_iops = max(0, (stat.read_count - prev.read_count)) / self._interval
                write_iops = max(0, (stat.write_count - prev.write_count)) / self._interval

                rates[stat.device] = {
                    "read_bytes_rate": read_bytes_rate,
                    "write_bytes_rate": write_bytes_rate,
                    "read_iops": read_iops,
                    "write_iops": write_iops,
                }

        return rates

    def compose(self) -> ComposeResult:
        """Compose the I/O stats display."""
        if not self._io_stats:
            return

        yield Label("Disk I/O", classes="io-header")

        rates = self._calculate_rates()

        for stat in self._io_stats:
            device_rates = rates.get(stat.device)
            if device_rates:
                read_rate = format_rate(device_rates["read_bytes_rate"])
                write_rate = format_rate(device_rates["write_bytes_rate"])
                read_iops = int(device_rates["read_iops"])
                write_iops = int(device_rates["write_iops"])

                yield Label(
                    f"{stat.device}: R: {read_rate} ({read_iops} IOPS) | "
                    f"W: {write_rate} ({write_iops} IOPS)",
                    classes="io-stats-line",
                )
            else:
                # Show cumulative totals if no rates available
                read_total = format_bytes(stat.read_bytes)
                write_total = format_bytes(stat.write_bytes)
                yield Label(
                    f"{stat.device}: R: {read_total} (total) | W: {write_total} (total)",
                    classes="io-stats-line",
                )


class DiskWidget(Widget):
    """Main disk widget displaying filesystem usage and I/O stats.

    Displays:
    - Per-mount filesystem usage with progress bars
    - Color-coded usage indicators (green < 70%, yellow 70-90%, red > 90%)
    - Disk I/O statistics when available

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
        height: auto;
        padding: 0;
    }

    DiskWidget .no-data {
        width: 100%;
        height: 3;
        content-align: center middle;
        color: $text-muted;
    }

    DiskWidget .partitions-container {
        width: 100%;
        height: auto;
    }
    """

    # Reactive property for data - triggers re-render on change
    data: reactive[DiskData | None] = reactive(None)
    prev_data: reactive[DiskData | None] = reactive(None)
    refresh_interval: reactive[float] = reactive(5.0)

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

    def compose(self) -> ComposeResult:
        """Compose the disk widget."""
        if self.data is None:
            yield Label("No disk data available", classes="no-data")
            return

        # Partitions container
        with Vertical(classes="partitions-container"):
            for partition in self.data.partitions:
                yield PartitionDisplay(partition)

        # I/O stats (if available)
        if self.data.io_stats:
            prev_io_stats = self.prev_data.io_stats if self.prev_data else None
            yield IOStatsDisplay(
                self.data.io_stats,
                prev_io_stats=prev_io_stats,
                interval=self.refresh_interval,
            )

    def update_data(self, new_data: DiskData) -> None:
        """Update the widget with new disk data.

        Args:
            new_data: New DiskData to display
        """
        # Store current data as previous for rate calculations
        self.prev_data = self.data
        self.data = new_data
        self.refresh(recompose=True)

    def watch_data(self, new_data: DiskData | None) -> None:
        """React to data changes.

        Args:
            new_data: The new DiskData value
        """
        if self.is_mounted:
            self.refresh(recompose=True)
