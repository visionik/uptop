"""Disk monitoring pane plugin for uptop.

This module provides disk partition and I/O monitoring functionality:
- PartitionInfo: Information about mounted partitions (gauges - current state)
- DiskIOStats: I/O statistics per disk device (counters - cumulative since boot)
- DiskData: Aggregated disk metrics
- DiskCollector: Data collector for disk metrics
- DiskPane: TUI pane plugin for disk monitoring
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import psutil
from pydantic import BaseModel, ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import DisplayMode, MetricData, counter_field, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget


# Virtual filesystem types to exclude from partition listing
VIRTUAL_FILESYSTEMS = frozenset(
    {
        "devfs",
        "devtmpfs",
        "tmpfs",
        "proc",
        "sysfs",
        "cgroup",
        "cgroup2",
        "pstore",
        "securityfs",
        "debugfs",
        "configfs",
        "fusectl",
        "hugetlbfs",
        "mqueue",
        "binfmt_misc",
        "autofs",
        "overlay",
        "squashfs",
        "snap",
    }
)


class PartitionInfo(BaseModel):
    """Information about a mounted disk partition.

    All usage fields are gauges representing current state.

    Attributes:
        device: Device path (e.g., /dev/sda1)
        mountpoint: Mount location (e.g., /home)
        fstype: Filesystem type (e.g., ext4, ntfs)
        opts: Mount options string
        total_bytes: Total partition size in bytes [gauge]
        used_bytes: Used space in bytes [gauge]
        free_bytes: Free space in bytes [gauge]
        percent: Usage percentage (0.0 to 100.0) [gauge]
    """

    model_config = ConfigDict(frozen=True)

    device: str = Field(..., description="Device path")
    mountpoint: str = Field(..., description="Mount location")
    fstype: str = Field(..., description="Filesystem type")
    opts: str = Field(default="", description="Mount options")
    total_bytes: int = gauge_field("Total size in bytes", ge=0)
    used_bytes: int = gauge_field("Used space in bytes", ge=0)
    free_bytes: int = gauge_field("Free space in bytes", ge=0)
    percent: float = gauge_field("Usage percentage", ge=0.0, le=100.0)


class DiskIOStats(BaseModel):
    """I/O statistics for a disk device.

    All I/O fields are counters (cumulative since boot, monotonically increasing).

    Attributes:
        device: Device name (e.g., sda, nvme0n1)
        read_bytes: Total bytes read since boot [counter]
        write_bytes: Total bytes written since boot [counter]
        read_count: Number of read operations [counter]
        write_count: Number of write operations [counter]
        read_time_ms: Time spent reading in milliseconds [counter]
        write_time_ms: Time spent writing in milliseconds [counter]
    """

    model_config = ConfigDict(frozen=True)

    device: str = Field(..., description="Device name")
    read_bytes: int = counter_field("Total bytes read since boot", ge=0)
    write_bytes: int = counter_field("Total bytes written since boot", ge=0)
    read_count: int = counter_field("Number of read operations since boot", ge=0)
    write_count: int = counter_field("Number of write operations since boot", ge=0)
    read_time_ms: int = counter_field("Read time in milliseconds since boot", ge=0)
    write_time_ms: int = counter_field("Write time in milliseconds since boot", ge=0)


class DiskData(MetricData):
    """Aggregated disk metrics.

    Contains information about all mounted partitions and I/O statistics
    for all disk devices.

    Attributes:
        partitions: List of partition information
        io_stats: List of I/O statistics per device
        partition_count: Number of partitions [gauge]
    """

    partitions: list[PartitionInfo] = Field(default_factory=list)
    io_stats: list[DiskIOStats] = Field(default_factory=list)
    partition_count: int = gauge_field("Number of partitions", default=0, ge=0)


class DiskCollector(DataCollector[DiskData]):
    """Collector for disk partition and I/O metrics.

    Uses psutil to gather:
    - Mounted partition information (excluding virtual filesystems)
    - Disk usage for each partition
    - Per-device I/O counters

    Handles PermissionError gracefully for inaccessible mountpoints.
    """

    name = "disk"
    default_interval = 5.0
    timeout = 10.0

    def __init__(self, exclude_virtual: bool = True) -> None:
        """Initialize the disk collector.

        Args:
            exclude_virtual: Whether to exclude virtual filesystems
        """
        super().__init__()
        self.exclude_virtual = exclude_virtual

    def _is_virtual_filesystem(self, partition: Any) -> bool:
        """Check if a partition is a virtual filesystem.

        Args:
            partition: psutil partition object

        Returns:
            True if the partition should be excluded
        """
        if not self.exclude_virtual:
            return False

        # Check filesystem type
        if partition.fstype.lower() in VIRTUAL_FILESYSTEMS:
            return True

        # Check if mountpoint is a special path
        mountpoint = partition.mountpoint.lower()
        return any(mountpoint.startswith(p) for p in ("/sys", "/proc", "/dev", "/run", "/snap"))

    def _get_partition_info(self, partition: Any) -> PartitionInfo | None:
        """Get partition info including disk usage.

        Args:
            partition: psutil partition object

        Returns:
            PartitionInfo or None if the partition is inaccessible
        """
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            return PartitionInfo(
                device=partition.device,
                mountpoint=partition.mountpoint,
                fstype=partition.fstype,
                opts=partition.opts,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=usage.percent,
            )
        except PermissionError:
            # Mountpoint is not accessible
            return None
        except OSError:
            # Other OS errors (e.g., device removed)
            return None

    def _get_io_stats(self) -> list[DiskIOStats]:
        """Get I/O statistics for all disk devices.

        Returns:
            List of DiskIOStats for each device
        """
        try:
            io_counters = psutil.disk_io_counters(perdisk=True)
            if io_counters is None:
                return []

            stats = []
            for device, counters in io_counters.items():
                stats.append(
                    DiskIOStats(
                        device=device,
                        read_bytes=counters.read_bytes,
                        write_bytes=counters.write_bytes,
                        read_count=counters.read_count,
                        write_count=counters.write_count,
                        read_time_ms=counters.read_time,
                        write_time_ms=counters.write_time,
                    )
                )
            return stats
        except (OSError, PermissionError):
            return []

    async def collect(self) -> DiskData:
        """Collect disk partition and I/O metrics.

        Returns:
            DiskData with current disk information
        """
        partitions: list[PartitionInfo] = []

        # Get mounted partitions (all=False excludes pseudo filesystems)
        for partition in psutil.disk_partitions(all=False):
            if self._is_virtual_filesystem(partition):
                continue

            info = self._get_partition_info(partition)
            if info is not None:
                partitions.append(info)

        io_stats = self._get_io_stats()

        return DiskData(
            source=self.name,
            partitions=partitions,
            io_stats=io_stats,
            partition_count=len(partitions),
        )

    def get_schema(self) -> type[DiskData]:
        """Return the Pydantic model class for disk data.

        Returns:
            DiskData class
        """
        return DiskData


class DiskPane(PanePlugin):
    """Disk monitoring pane plugin.

    Displays disk partition information and I/O statistics in the TUI.
    """

    name = "disk"
    display_name = "Disk"
    version = "0.1.0"
    description = "Monitor disk partitions and I/O statistics"
    author = "uptop"
    default_refresh_interval = 5.0

    def __init__(self) -> None:
        """Initialize the disk pane plugin."""
        super().__init__()
        self._collector = DiskCollector()
        self._cached_widget = None  # Cache widget to preserve state

    def shutdown(self) -> None:
        """Clean up resources."""
        self._cached_widget = None
        self._collector.shutdown()
        super().shutdown()

    async def collect_data(self) -> DiskData:
        """Collect current disk data.

        Returns:
            DiskData with current disk metrics
        """
        return await self._collector.collect()

    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> Widget:
        """Render disk data as a Textual widget.

        Args:
            data: The DiskData from the most recent collection
            size: Optional (width, height) in cells (currently unused)
            mode: Optional DisplayMode (currently unused, always full display)

        Returns:
            A Textual DiskWidget with partition and I/O info
        """
        from textual.widgets import Label

        from uptop.tui.panes.disk_widget import DiskWidget

        if not isinstance(data, DiskData):
            return Label("Invalid disk data")

        # Reuse cached widget to preserve state
        if self._cached_widget is None:
            self._cached_widget = DiskWidget()
        self._cached_widget.update_data(data, mode)
        return self._cached_widget

    def get_schema(self) -> type[DiskData]:
        """Return the Pydantic model class for disk data.

        Returns:
            DiskData class
        """
        return DiskData
