"""Tests for the Disk pane plugin."""

from collections import namedtuple
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
import pytest

from uptop.models import MetricData, MetricType, PluginType, get_metric_type
from uptop.plugins.disk import (
    VIRTUAL_FILESYSTEMS,
    DiskCollector,
    DiskData,
    DiskIOStats,
    DiskPane,
    PartitionInfo,
)

# Mock psutil types
MockPartition = namedtuple("sdiskpart", ["device", "mountpoint", "fstype", "opts"])
MockUsage = namedtuple("sdiskusage", ["total", "used", "free", "percent"])
MockIOCounters = namedtuple(
    "sdiskio",
    ["read_bytes", "write_bytes", "read_count", "write_count", "read_time", "write_time"],
)


# ============================================================================
# PartitionInfo Model Tests
# ============================================================================


class TestPartitionInfo:
    """Tests for PartitionInfo model."""

    def test_valid_partition_info(self) -> None:
        """Test creating valid partition info."""
        info = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            opts="rw,noatime",
            total_bytes=100000000000,
            used_bytes=50000000000,
            free_bytes=50000000000,
            percent=50.0,
        )

        assert info.device == "/dev/sda1"
        assert info.mountpoint == "/"
        assert info.fstype == "ext4"
        assert info.opts == "rw,noatime"
        assert info.total_bytes == 100000000000
        assert info.used_bytes == 50000000000
        assert info.free_bytes == 50000000000
        assert info.percent == 50.0

    def test_partition_info_default_opts(self) -> None:
        """Test that opts defaults to empty string."""
        info = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100,
            used_bytes=50,
            free_bytes=50,
            percent=50.0,
        )

        assert info.opts == ""

    def test_partition_info_frozen(self) -> None:
        """Test that PartitionInfo is immutable."""
        info = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100,
            used_bytes=50,
            free_bytes=50,
            percent=50.0,
        )

        with pytest.raises(ValidationError):
            info.device = "/dev/sda2"

    def test_partition_info_negative_bytes_invalid(self) -> None:
        """Test that negative byte values are rejected."""
        with pytest.raises(ValidationError):
            PartitionInfo(
                device="/dev/sda1",
                mountpoint="/",
                fstype="ext4",
                total_bytes=-100,
                used_bytes=50,
                free_bytes=50,
                percent=50.0,
            )

    def test_partition_info_percent_out_of_range(self) -> None:
        """Test that percent outside 0-100 is rejected."""
        with pytest.raises(ValidationError):
            PartitionInfo(
                device="/dev/sda1",
                mountpoint="/",
                fstype="ext4",
                total_bytes=100,
                used_bytes=50,
                free_bytes=50,
                percent=150.0,
            )

        with pytest.raises(ValidationError):
            PartitionInfo(
                device="/dev/sda1",
                mountpoint="/",
                fstype="ext4",
                total_bytes=100,
                used_bytes=50,
                free_bytes=50,
                percent=-10.0,
            )


# ============================================================================
# DiskIOStats Model Tests
# ============================================================================


class TestDiskIOStats:
    """Tests for DiskIOStats model."""

    def test_valid_io_stats(self) -> None:
        """Test creating valid I/O stats."""
        stats = DiskIOStats(
            device="sda",
            read_bytes=1000000,
            write_bytes=500000,
            read_count=100,
            write_count=50,
            read_time_ms=1000,
            write_time_ms=500,
        )

        assert stats.device == "sda"
        assert stats.read_bytes == 1000000
        assert stats.write_bytes == 500000
        assert stats.read_count == 100
        assert stats.write_count == 50
        assert stats.read_time_ms == 1000
        assert stats.write_time_ms == 500

    def test_io_stats_frozen(self) -> None:
        """Test that DiskIOStats is immutable."""
        stats = DiskIOStats(
            device="sda",
            read_bytes=1000,
            write_bytes=500,
            read_count=10,
            write_count=5,
            read_time_ms=100,
            write_time_ms=50,
        )

        with pytest.raises(ValidationError):
            stats.device = "sdb"

    def test_io_stats_negative_values_invalid(self) -> None:
        """Test that negative values are rejected."""
        with pytest.raises(ValidationError):
            DiskIOStats(
                device="sda",
                read_bytes=-1000,
                write_bytes=500,
                read_count=10,
                write_count=5,
                read_time_ms=100,
                write_time_ms=50,
            )


# ============================================================================
# DiskData Model Tests
# ============================================================================


class TestDiskData:
    """Tests for DiskData model."""

    def test_disk_data_defaults(self) -> None:
        """Test DiskData default values."""
        data = DiskData()

        assert data.partitions == []
        assert data.io_stats == []
        assert data.partition_count == 0
        assert isinstance(data.timestamp, object)
        assert data.source == "unknown"

    def test_disk_data_with_partitions(self) -> None:
        """Test DiskData with partition list."""
        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100,
            used_bytes=50,
            free_bytes=50,
            percent=50.0,
        )

        data = DiskData(
            partitions=[partition],
            partition_count=1,
            source="disk",
        )

        assert len(data.partitions) == 1
        assert data.partitions[0].device == "/dev/sda1"
        assert data.partition_count == 1
        assert data.source == "disk"

    def test_disk_data_with_io_stats(self) -> None:
        """Test DiskData with I/O stats."""
        io_stat = DiskIOStats(
            device="sda",
            read_bytes=1000,
            write_bytes=500,
            read_count=10,
            write_count=5,
            read_time_ms=100,
            write_time_ms=50,
        )

        data = DiskData(io_stats=[io_stat])

        assert len(data.io_stats) == 1
        assert data.io_stats[0].device == "sda"

    def test_disk_data_inherits_metric_data(self) -> None:
        """Test that DiskData inherits from MetricData."""
        data = DiskData()
        assert isinstance(data, MetricData)

    def test_disk_data_age_seconds(self) -> None:
        """Test age_seconds method inherited from MetricData."""
        data = DiskData()
        age = data.age_seconds()
        assert age >= 0
        assert age < 1  # Should be very recent

    def test_disk_data_negative_partition_count_invalid(self) -> None:
        """Test that negative partition count is rejected."""
        with pytest.raises(ValidationError):
            DiskData(partition_count=-1)


# ============================================================================
# Metric Type Tests
# ============================================================================


class TestDiskMetricTypes:
    """Tests for metric type annotations on Disk models."""

    def test_partition_info_metric_types(self) -> None:
        """Test that PartitionInfo fields have correct metric types (all gauges)."""
        assert get_metric_type(PartitionInfo, "total_bytes") == MetricType.GAUGE
        assert get_metric_type(PartitionInfo, "used_bytes") == MetricType.GAUGE
        assert get_metric_type(PartitionInfo, "free_bytes") == MetricType.GAUGE
        assert get_metric_type(PartitionInfo, "percent") == MetricType.GAUGE
        # Non-metric fields
        assert get_metric_type(PartitionInfo, "device") is None
        assert get_metric_type(PartitionInfo, "mountpoint") is None

    def test_disk_io_stats_metric_types(self) -> None:
        """Test that DiskIOStats fields have correct metric types (all counters)."""
        assert get_metric_type(DiskIOStats, "read_bytes") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "write_bytes") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "read_count") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "write_count") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "read_time_ms") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "write_time_ms") == MetricType.COUNTER
        # Non-metric fields
        assert get_metric_type(DiskIOStats, "device") is None

    def test_disk_data_metric_types(self) -> None:
        """Test that DiskData fields have correct metric types."""
        assert get_metric_type(DiskData, "partition_count") == MetricType.GAUGE


# ============================================================================
# DiskCollector Tests
# ============================================================================


class TestDiskCollector:
    """Tests for DiskCollector."""

    def test_collector_attributes(self) -> None:
        """Test collector class attributes."""
        collector = DiskCollector()

        assert collector.name == "disk"
        assert collector.default_interval == 5.0
        assert collector.timeout == 10.0

    def test_collector_exclude_virtual_default(self) -> None:
        """Test that exclude_virtual defaults to True."""
        collector = DiskCollector()
        assert collector.exclude_virtual is True

    def test_collector_exclude_virtual_false(self) -> None:
        """Test setting exclude_virtual to False."""
        collector = DiskCollector(exclude_virtual=False)
        assert collector.exclude_virtual is False

    def test_is_virtual_filesystem_by_fstype(self) -> None:
        """Test detection of virtual filesystems by type."""
        collector = DiskCollector()

        # Virtual filesystem
        virtual_partition = MockPartition(
            device="tmpfs",
            mountpoint="/tmp",
            fstype="tmpfs",
            opts="rw",
        )
        assert collector._is_virtual_filesystem(virtual_partition) is True

        # Real filesystem
        real_partition = MockPartition(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            opts="rw",
        )
        assert collector._is_virtual_filesystem(real_partition) is False

    def test_is_virtual_filesystem_by_mountpoint(self) -> None:
        """Test detection of virtual filesystems by mountpoint."""
        collector = DiskCollector()

        # Virtual mountpoint
        sys_partition = MockPartition(
            device="sysfs",
            mountpoint="/sys/something",
            fstype="sysfs",
            opts="rw",
        )
        assert collector._is_virtual_filesystem(sys_partition) is True

        proc_partition = MockPartition(
            device="proc",
            mountpoint="/proc",
            fstype="proc",
            opts="rw",
        )
        assert collector._is_virtual_filesystem(proc_partition) is True

    def test_is_virtual_filesystem_disabled(self) -> None:
        """Test that virtual filesystem filtering can be disabled."""
        collector = DiskCollector(exclude_virtual=False)

        virtual_partition = MockPartition(
            device="tmpfs",
            mountpoint="/tmp",
            fstype="tmpfs",
            opts="rw",
        )
        assert collector._is_virtual_filesystem(virtual_partition) is False

    @patch("uptop.plugins.disk.psutil.disk_usage")
    def test_get_partition_info_success(self, mock_usage: MagicMock) -> None:
        """Test successful partition info retrieval."""
        mock_usage.return_value = MockUsage(
            total=1000000000,
            used=500000000,
            free=500000000,
            percent=50.0,
        )

        collector = DiskCollector()
        partition = MockPartition(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            opts="rw,noatime",
        )

        info = collector._get_partition_info(partition)

        assert info is not None
        assert info.device == "/dev/sda1"
        assert info.mountpoint == "/"
        assert info.total_bytes == 1000000000
        assert info.percent == 50.0

    @patch("uptop.plugins.disk.psutil.disk_usage")
    def test_get_partition_info_permission_error(self, mock_usage: MagicMock) -> None:
        """Test handling of PermissionError."""
        mock_usage.side_effect = PermissionError("Access denied")

        collector = DiskCollector()
        partition = MockPartition(
            device="/dev/sda1",
            mountpoint="/restricted",
            fstype="ext4",
            opts="rw",
        )

        info = collector._get_partition_info(partition)
        assert info is None

    @patch("uptop.plugins.disk.psutil.disk_usage")
    def test_get_partition_info_os_error(self, mock_usage: MagicMock) -> None:
        """Test handling of OSError."""
        mock_usage.side_effect = OSError("Device removed")

        collector = DiskCollector()
        partition = MockPartition(
            device="/dev/sdb1",
            mountpoint="/mnt/usb",
            fstype="vfat",
            opts="rw",
        )

        info = collector._get_partition_info(partition)
        assert info is None

    @patch("uptop.plugins.disk.psutil.disk_io_counters")
    def test_get_io_stats_success(self, mock_io: MagicMock) -> None:
        """Test successful I/O stats retrieval."""
        mock_io.return_value = {
            "sda": MockIOCounters(
                read_bytes=1000000,
                write_bytes=500000,
                read_count=100,
                write_count=50,
                read_time=1000,
                write_time=500,
            ),
            "sdb": MockIOCounters(
                read_bytes=2000000,
                write_bytes=1000000,
                read_count=200,
                write_count=100,
                read_time=2000,
                write_time=1000,
            ),
        }

        collector = DiskCollector()
        stats = collector._get_io_stats()

        assert len(stats) == 2
        devices = {s.device for s in stats}
        assert devices == {"sda", "sdb"}

    @patch("uptop.plugins.disk.psutil.disk_io_counters")
    def test_get_io_stats_none(self, mock_io: MagicMock) -> None:
        """Test handling when disk_io_counters returns None."""
        mock_io.return_value = None

        collector = DiskCollector()
        stats = collector._get_io_stats()

        assert stats == []

    @patch("uptop.plugins.disk.psutil.disk_io_counters")
    def test_get_io_stats_os_error(self, mock_io: MagicMock) -> None:
        """Test handling of OSError in I/O stats."""
        mock_io.side_effect = OSError("Failed to get I/O counters")

        collector = DiskCollector()
        stats = collector._get_io_stats()

        assert stats == []

    @pytest.mark.asyncio
    @patch("uptop.plugins.disk.psutil.disk_partitions")
    @patch("uptop.plugins.disk.psutil.disk_usage")
    @patch("uptop.plugins.disk.psutil.disk_io_counters")
    async def test_collect(
        self,
        mock_io: MagicMock,
        mock_usage: MagicMock,
        mock_partitions: MagicMock,
    ) -> None:
        """Test full collection process."""
        mock_partitions.return_value = [
            MockPartition("/dev/sda1", "/", "ext4", "rw"),
            MockPartition("/dev/sda2", "/home", "ext4", "rw"),
            MockPartition("tmpfs", "/tmp", "tmpfs", "rw"),  # Virtual, should be excluded
        ]

        mock_usage.return_value = MockUsage(
            total=1000000000,
            used=500000000,
            free=500000000,
            percent=50.0,
        )

        mock_io.return_value = {
            "sda": MockIOCounters(1000, 500, 10, 5, 100, 50),
        }

        collector = DiskCollector()
        data = await collector.collect()

        assert isinstance(data, DiskData)
        assert data.source == "disk"
        # Should have 2 partitions (tmpfs excluded)
        assert data.partition_count == 2
        assert len(data.partitions) == 2
        assert len(data.io_stats) == 1

    def test_get_schema(self) -> None:
        """Test get_schema returns DiskData."""
        collector = DiskCollector()
        assert collector.get_schema() == DiskData


# ============================================================================
# DiskPane Tests
# ============================================================================


class TestDiskPane:
    """Tests for DiskPane plugin."""

    def test_pane_attributes(self) -> None:
        """Test pane class attributes."""
        pane = DiskPane()

        assert pane.name == "disk"
        assert pane.display_name == "Disk"
        assert pane.version == "0.1.0"
        assert pane.description == "Monitor disk partitions and I/O statistics"
        assert pane.author == "uptop"
        assert pane.default_refresh_interval == 5.0

    def test_pane_plugin_type(self) -> None:
        """Test that DiskPane returns PANE plugin type."""
        assert DiskPane.get_plugin_type() == PluginType.PANE

    def test_pane_has_collector(self) -> None:
        """Test that pane creates a collector."""
        pane = DiskPane()
        assert isinstance(pane._collector, DiskCollector)

    @pytest.mark.asyncio
    @patch("uptop.plugins.disk.psutil.disk_partitions")
    @patch("uptop.plugins.disk.psutil.disk_usage")
    @patch("uptop.plugins.disk.psutil.disk_io_counters")
    async def test_collect_data(
        self,
        mock_io: MagicMock,
        mock_usage: MagicMock,
        mock_partitions: MagicMock,
    ) -> None:
        """Test collect_data method."""
        mock_partitions.return_value = [
            MockPartition("/dev/sda1", "/", "ext4", "rw"),
        ]
        mock_usage.return_value = MockUsage(1000, 500, 500, 50.0)
        mock_io.return_value = {}

        pane = DiskPane()
        data = await pane.collect_data()

        assert isinstance(data, DiskData)
        assert data.partition_count == 1

    def test_render_tui_valid_data(self) -> None:
        """Test render_tui with valid data."""
        pane = DiskPane()

        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=1000000000000,  # ~1TB
            used_bytes=500000000000,
            free_bytes=500000000000,
            percent=50.0,
        )

        data = DiskData(
            partitions=[partition],
            partition_count=1,
        )

        widget = pane.render_tui(data)

        from uptop.tui.panes.disk_widget import DiskWidget

        assert isinstance(widget, DiskWidget)
        assert hasattr(widget, "update_data")

    def test_render_tui_invalid_data(self) -> None:
        """Test render_tui with invalid data type."""
        pane = DiskPane()

        # Pass a base MetricData instead of DiskData
        data = MetricData()

        widget = pane.render_tui(data)

        from textual.widgets import Label

        assert isinstance(widget, Label)

    def test_get_schema(self) -> None:
        """Test get_schema returns DiskData."""
        pane = DiskPane()
        assert pane.get_schema() == DiskData

    def test_get_metadata(self) -> None:
        """Test metadata generation."""
        meta = DiskPane.get_metadata()

        assert meta.name == "disk"
        assert meta.display_name == "Disk"
        assert meta.plugin_type == PluginType.PANE
        assert meta.version == "0.1.0"

    def test_initialize_and_shutdown(self) -> None:
        """Test plugin lifecycle methods."""
        pane = DiskPane()

        # Initialize
        pane.initialize({"custom_setting": "value"})
        assert pane._initialized is True
        assert pane.config == {"custom_setting": "value"}

        # Shutdown
        pane.shutdown()
        assert pane._initialized is False


# ============================================================================
# Virtual Filesystem Constants Tests
# ============================================================================


class TestVirtualFilesystems:
    """Tests for virtual filesystem detection."""

    def test_virtual_filesystems_set(self) -> None:
        """Test that VIRTUAL_FILESYSTEMS is a frozenset."""
        assert isinstance(VIRTUAL_FILESYSTEMS, frozenset)

    def test_common_virtual_filesystems_included(self) -> None:
        """Test that common virtual filesystems are in the set."""
        expected = {"tmpfs", "proc", "sysfs", "devtmpfs", "cgroup", "cgroup2"}
        assert expected.issubset(VIRTUAL_FILESYSTEMS)

    def test_real_filesystems_not_included(self) -> None:
        """Test that real filesystems are not in the set."""
        real_fs = {"ext4", "xfs", "btrfs", "ntfs", "apfs", "hfs+"}
        for fs in real_fs:
            assert fs not in VIRTUAL_FILESYSTEMS
