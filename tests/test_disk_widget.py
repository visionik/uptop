"""Tests for the Disk Widget."""

from uptop.plugins.disk import DiskData, DiskIOStats, PartitionInfo
from uptop.tui.panes.disk_widget import (
    DiskWidget,
    PartitionDisplay,
    format_bytes,
    format_iops,
    get_usage_color,
)

# ============================================================================
# format_bytes Tests
# ============================================================================


class TestFormatBytes:
    """Tests for format_bytes helper function.

    Note: format_bytes now matches network widget style:
    - Always at least KB (no plain bytes)
    - No space between number and unit
    """

    def test_format_zero_bytes(self) -> None:
        """Test formatting zero bytes (shows as 0.0KB)."""
        assert format_bytes(0) == "0.0KB"

    def test_format_negative_bytes(self) -> None:
        """Test formatting negative bytes (edge case, treated as 0)."""
        assert format_bytes(-100) == "0.0KB"

    def test_format_bytes_under_kb(self) -> None:
        """Test formatting bytes under 1 KB (still shows as KB)."""
        assert format_bytes(512) == "0.5KB"
        assert format_bytes(1023) == "1.0KB"

    def test_format_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_bytes(1024) == "1.0KB"
        assert format_bytes(1536) == "1.5KB"
        assert format_bytes(10240) == "10.0KB"

    def test_format_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_bytes(1024 * 1024) == "1.0MB"
        assert format_bytes(1024 * 1024 * 256) == "256.0MB"

    def test_format_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_bytes(1024**3) == "1.0GB"
        assert format_bytes(1024**3 * 16) == "16.0GB"

    def test_format_terabytes(self) -> None:
        """Test formatting terabytes."""
        assert format_bytes(1024**4) == "1.0TB"
        assert format_bytes(1024**4 * 2) == "2.0TB"

    def test_format_petabytes(self) -> None:
        """Test formatting petabytes."""
        assert format_bytes(1024**5) == "1.0PB"


# ============================================================================
# get_usage_color Tests
# ============================================================================


class TestGetUsageColor:
    """Tests for get_usage_color helper function."""

    def test_low_usage_green(self) -> None:
        """Test that usage below 70% returns green color class."""
        assert get_usage_color(0.0) == "usage-low"
        assert get_usage_color(50.0) == "usage-low"
        assert get_usage_color(69.9) == "usage-low"

    def test_medium_usage_yellow(self) -> None:
        """Test that usage 70-89% returns yellow color class."""
        assert get_usage_color(70.0) == "usage-medium"
        assert get_usage_color(80.0) == "usage-medium"
        assert get_usage_color(89.9) == "usage-medium"

    def test_high_usage_red(self) -> None:
        """Test that usage 90%+ returns red color class."""
        assert get_usage_color(90.0) == "usage-high"
        assert get_usage_color(95.0) == "usage-high"
        assert get_usage_color(100.0) == "usage-high"

    def test_edge_case_exactly_70(self) -> None:
        """Test usage exactly at 70% boundary."""
        assert get_usage_color(70.0) == "usage-medium"

    def test_edge_case_exactly_90(self) -> None:
        """Test usage exactly at 90% boundary."""
        assert get_usage_color(90.0) == "usage-high"


# ============================================================================
# DiskWidget Tests
# ============================================================================


class TestDiskWidget:
    """Tests for DiskWidget."""

    def test_widget_instantiation_no_data(self) -> None:
        """Test widget can be instantiated without data."""
        widget = DiskWidget()

        assert widget.data is None
        assert widget.prev_data is None
        assert widget.refresh_interval == 5.0

    def test_widget_instantiation_with_data(self) -> None:
        """Test widget can be instantiated with DiskData."""
        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100000000000,
            used_bytes=50000000000,
            free_bytes=50000000000,
            percent=50.0,
        )

        data = DiskData(
            partitions=[partition],
            partition_count=1,
            source="disk",
        )

        widget = DiskWidget(data=data)

        assert widget.data is not None
        assert widget.data.partition_count == 1
        assert len(widget.data.partitions) == 1

    def test_widget_instantiation_with_refresh_interval(self) -> None:
        """Test widget with custom refresh interval."""
        widget = DiskWidget(refresh_interval=10.0)
        assert widget.refresh_interval == 10.0

    def test_widget_update_data(self) -> None:
        """Test update_data method."""
        widget = DiskWidget()

        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100000000000,
            used_bytes=50000000000,
            free_bytes=50000000000,
            percent=50.0,
        )

        data = DiskData(
            partitions=[partition],
            partition_count=1,
            source="disk",
        )

        # Update with first data
        widget.update_data(data)

        assert widget.data is not None
        assert widget.prev_data is None  # First update has no previous

        # Update with second data
        new_partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100000000000,
            used_bytes=60000000000,
            free_bytes=40000000000,
            percent=60.0,
        )

        new_data = DiskData(
            partitions=[new_partition],
            partition_count=1,
            source="disk",
        )

        widget.update_data(new_data)

        assert widget.data.partitions[0].percent == 60.0
        assert widget.prev_data is not None
        assert widget.prev_data.partitions[0].percent == 50.0

    def test_widget_with_io_stats(self) -> None:
        """Test widget with I/O statistics."""
        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100000000000,
            used_bytes=50000000000,
            free_bytes=50000000000,
            percent=50.0,
        )

        io_stat = DiskIOStats(
            device="sda",
            read_bytes=1000000000,
            write_bytes=500000000,
            read_count=10000,
            write_count=5000,
            read_time_ms=10000,
            write_time_ms=5000,
        )

        data = DiskData(
            partitions=[partition],
            io_stats=[io_stat],
            partition_count=1,
            source="disk",
        )

        widget = DiskWidget(data=data)

        assert widget.data is not None
        assert len(widget.data.io_stats) == 1
        assert widget.data.io_stats[0].device == "sda"

    def test_widget_with_multiple_partitions(self) -> None:
        """Test widget with multiple partitions."""
        partitions = [
            PartitionInfo(
                device="/dev/sda1",
                mountpoint="/",
                fstype="ext4",
                total_bytes=100000000000,
                used_bytes=30000000000,
                free_bytes=70000000000,
                percent=30.0,
            ),
            PartitionInfo(
                device="/dev/sda2",
                mountpoint="/home",
                fstype="ext4",
                total_bytes=500000000000,
                used_bytes=400000000000,
                free_bytes=100000000000,
                percent=80.0,
            ),
            PartitionInfo(
                device="/dev/sdb1",
                mountpoint="/data",
                fstype="xfs",
                total_bytes=1000000000000,
                used_bytes=950000000000,
                free_bytes=50000000000,
                percent=95.0,
            ),
        ]

        data = DiskData(
            partitions=partitions,
            partition_count=3,
            source="disk",
        )

        widget = DiskWidget(data=data)

        assert widget.data is not None
        assert widget.data.partition_count == 3

        # Check color coding for different usage levels
        assert get_usage_color(partitions[0].percent) == "usage-low"
        assert get_usage_color(partitions[1].percent) == "usage-medium"
        assert get_usage_color(partitions[2].percent) == "usage-high"


# ============================================================================
# PartitionDisplay Tests
# ============================================================================


class TestPartitionDisplay:
    """Tests for PartitionDisplay widget."""

    def test_partition_display_instantiation(self) -> None:
        """Test PartitionDisplay can be instantiated."""
        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100000000000,
            used_bytes=50000000000,
            free_bytes=50000000000,
            percent=50.0,
        )

        display = PartitionDisplay(partition)

        assert display._partition is partition

    def test_partition_display_with_id(self) -> None:
        """Test PartitionDisplay with custom ID."""
        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100000000000,
            used_bytes=50000000000,
            free_bytes=50000000000,
            percent=50.0,
        )

        display = PartitionDisplay(partition, id="root-partition")

        assert display.id == "root-partition"


# ============================================================================
# format_iops Tests
# ============================================================================


class TestFormatIops:
    """Tests for format_iops helper function."""

    def test_format_iops_zero(self) -> None:
        """Test formatting zero IOPS."""
        assert format_iops(0) == "0"

    def test_format_iops_under_thousand(self) -> None:
        """Test formatting IOPS under 1000."""
        assert format_iops(1) == "1"
        assert format_iops(500) == "500"
        assert format_iops(999) == "999"

    def test_format_iops_thousands(self) -> None:
        """Test formatting thousands of IOPS."""
        assert format_iops(1000) == "1.0K"
        assert format_iops(1500) == "1.5K"
        assert format_iops(10000) == "10.0K"
        assert format_iops(999999) == "1000.0K"

    def test_format_iops_millions(self) -> None:
        """Test formatting millions of IOPS."""
        assert format_iops(1000000) == "1.0M"
        assert format_iops(2500000) == "2.5M"


# ============================================================================
# DiskWidget Rate Calculation Tests
# ============================================================================


class TestDiskWidgetRateCalculation:
    """Tests for DiskWidget rate calculation."""

    def test_rate_calculation_with_prev_data(self) -> None:
        """Test rate calculation with previous data."""
        prev_stats = [
            DiskIOStats(
                device="sda",
                read_bytes=1000000,
                write_bytes=500000,
                read_count=100,
                write_count=50,
                read_time_ms=1000,
                write_time_ms=500,
            ),
        ]

        current_stats = [
            DiskIOStats(
                device="sda",
                read_bytes=2000000,
                write_bytes=1000000,
                read_count=200,
                write_count=100,
                read_time_ms=2000,
                write_time_ms=1000,
            ),
        ]

        prev_data = DiskData(
            partitions=[],
            io_stats=prev_stats,
            partition_count=0,
            source="disk",
        )

        current_data = DiskData(
            partitions=[],
            io_stats=current_stats,
            partition_count=0,
            source="disk",
        )

        widget = DiskWidget(refresh_interval=5.0)
        widget.prev_data = prev_data
        widget.data = current_data

        rates = widget._calculate_rates()

        # Read rate: (2000000 - 1000000) / 5.0 = 200000 bytes/sec
        assert "sda" in rates
        assert rates["sda"]["read_bytes_rate"] == 200000.0
        assert rates["sda"]["write_bytes_rate"] == 100000.0
        assert rates["sda"]["read_iops"] == 20.0
        assert rates["sda"]["write_iops"] == 10.0

    def test_rate_calculation_no_prev_data(self) -> None:
        """Test rate calculation without previous data."""
        io_stats = [
            DiskIOStats(
                device="sda",
                read_bytes=1000000,
                write_bytes=500000,
                read_count=100,
                write_count=50,
                read_time_ms=1000,
                write_time_ms=500,
            ),
        ]

        data = DiskData(
            partitions=[],
            io_stats=io_stats,
            partition_count=0,
            source="disk",
        )

        widget = DiskWidget()
        widget.data = data

        rates = widget._calculate_rates()

        # Without previous data, rates should be empty
        assert rates == {}

    def test_rate_calculation_multiple_devices(self) -> None:
        """Test rate calculation with multiple devices."""
        prev_stats = [
            DiskIOStats(
                device="sda",
                read_bytes=1000000,
                write_bytes=500000,
                read_count=100,
                write_count=50,
                read_time_ms=1000,
                write_time_ms=500,
            ),
            DiskIOStats(
                device="sdb",
                read_bytes=2000000,
                write_bytes=1000000,
                read_count=200,
                write_count=100,
                read_time_ms=2000,
                write_time_ms=1000,
            ),
        ]

        current_stats = [
            DiskIOStats(
                device="sda",
                read_bytes=2000000,
                write_bytes=1000000,
                read_count=200,
                write_count=100,
                read_time_ms=2000,
                write_time_ms=1000,
            ),
            DiskIOStats(
                device="sdb",
                read_bytes=4000000,
                write_bytes=2000000,
                read_count=400,
                write_count=200,
                read_time_ms=4000,
                write_time_ms=2000,
            ),
        ]

        prev_data = DiskData(
            partitions=[],
            io_stats=prev_stats,
            partition_count=0,
            source="disk",
        )

        current_data = DiskData(
            partitions=[],
            io_stats=current_stats,
            partition_count=0,
            source="disk",
        )

        widget = DiskWidget(refresh_interval=1.0)
        widget.prev_data = prev_data
        widget.data = current_data

        rates = widget._calculate_rates()

        assert "sda" in rates
        assert "sdb" in rates
        assert rates["sda"]["read_bytes_rate"] == 1000000.0
        assert rates["sdb"]["read_bytes_rate"] == 2000000.0


# ============================================================================
# Integration Tests
# ============================================================================


class TestDiskWidgetIntegration:
    """Integration tests for DiskWidget with real-world scenarios."""

    def test_typical_linux_system(self) -> None:
        """Test widget with typical Linux partition setup."""
        partitions = [
            PartitionInfo(
                device="/dev/nvme0n1p1",
                mountpoint="/",
                fstype="ext4",
                total_bytes=256 * 1024**3,  # 256 GB
                used_bytes=64 * 1024**3,  # 64 GB
                free_bytes=192 * 1024**3,  # 192 GB
                percent=25.0,
            ),
            PartitionInfo(
                device="/dev/nvme0n1p2",
                mountpoint="/home",
                fstype="ext4",
                total_bytes=512 * 1024**3,  # 512 GB
                used_bytes=384 * 1024**3,  # 384 GB
                free_bytes=128 * 1024**3,  # 128 GB
                percent=75.0,
            ),
        ]

        io_stats = [
            DiskIOStats(
                device="nvme0n1",
                read_bytes=100 * 1024**3,  # 100 GB total read
                write_bytes=50 * 1024**3,  # 50 GB total write
                read_count=1000000,
                write_count=500000,
                read_time_ms=10000000,
                write_time_ms=5000000,
            ),
        ]

        data = DiskData(
            partitions=partitions,
            io_stats=io_stats,
            partition_count=2,
            source="disk",
        )

        widget = DiskWidget(data=data, refresh_interval=5.0)

        assert widget.data is not None
        assert widget.data.partition_count == 2
        assert len(widget.data.io_stats) == 1

        # Verify human-readable formatting (no space, network widget style)
        assert format_bytes(partitions[0].total_bytes) == "256.0GB"
        assert format_bytes(partitions[1].total_bytes) == "512.0GB"

    def test_critical_disk_space(self) -> None:
        """Test widget display for critical disk space situation."""
        partition = PartitionInfo(
            device="/dev/sda1",
            mountpoint="/",
            fstype="ext4",
            total_bytes=100 * 1024**3,  # 100 GB
            used_bytes=98 * 1024**3,  # 98 GB
            free_bytes=2 * 1024**3,  # 2 GB free
            percent=98.0,
        )

        data = DiskData(
            partitions=[partition],
            partition_count=1,
            source="disk",
        )

        widget = DiskWidget(data=data)

        # Should show red/high usage color
        assert get_usage_color(widget.data.partitions[0].percent) == "usage-high"
        assert format_bytes(partition.free_bytes) == "2.0GB"
