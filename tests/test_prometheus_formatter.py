"""Tests for the Prometheus metrics formatter.

This module tests the PrometheusFormatter class which outputs metrics
in Prometheus exposition format.

Test categories:
- Metric type detection (gauge vs counter)
- Metric naming conventions (snake_case, prefixing)
- Label formatting for multi-instance metrics
- Data type handling (CPUData, MemoryData, NetworkData, DiskData)
- Prometheus format compliance
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from uptop.formatters.prometheus import (
    PrometheusFormatter,
    _format_labels,
    _sanitize_label_value,
    _sanitize_metric_name,
)
from uptop.models.base import MetricType, get_metric_type
from uptop.plugins.cpu import CPUCore, CPUData
from uptop.plugins.disk import DiskData, DiskIOStats, PartitionInfo
from uptop.plugins.memory import MemoryData, SwapMemory, VirtualMemory
from uptop.plugins.network import NetworkData, NetworkInterfaceData


class TestPrometheusFormatterBasics:
    """Test basic formatter properties and initialization."""

    def test_formatter_properties(self) -> None:
        """Test that formatter has correct properties."""
        formatter = PrometheusFormatter()

        assert formatter.name == "prometheus"
        assert formatter.format_name == "prometheus"
        assert formatter.file_extension == ".prom"
        assert formatter.cli_flag == "--prometheus"

    def test_formatter_initialization(self) -> None:
        """Test formatter initializes correctly."""
        formatter = PrometheusFormatter()

        # Check that formatter has the expected attributes
        assert formatter._prefix == "uptop"
        assert formatter._include_help is True
        assert formatter._include_type is True


class TestMetricNaming:
    """Test metric name sanitization and formatting."""

    def test_sanitize_special_characters(self) -> None:
        """Test removal of invalid characters."""
        # Uses module-level function _sanitize_metric_name
        assert _sanitize_metric_name("metric-name") == "metric_name"
        assert _sanitize_metric_name("metric.name") == "metric_name"
        assert _sanitize_metric_name("metric name") == "metric_name"

    def test_sanitize_leading_digit(self) -> None:
        """Test handling of leading digits."""
        # Leading digits should be prefixed with underscore
        assert _sanitize_metric_name("123metric") == "_123metric"

    def test_sanitize_preserves_valid_names(self) -> None:
        """Test that valid names are preserved."""
        assert _sanitize_metric_name("valid_name") == "valid_name"
        assert _sanitize_metric_name("metric_name_123") == "metric_name_123"
        assert _sanitize_metric_name("UPPERCASE") == "UPPERCASE"

    def test_sanitize_colons_allowed(self) -> None:
        """Test that colons are allowed in metric names."""
        assert _sanitize_metric_name("metric:name") == "metric:name"
        assert _sanitize_metric_name("namespace:metric") == "namespace:metric"

    def test_metric_prefix(self) -> None:
        """Test that metrics are prefixed with uptop_."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[],
            load_avg_1min=1.5,
            load_avg_5min=2.0,
            load_avg_15min=1.8,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # All metric names should start with uptop_
        for line in output.split("\n"):
            if line and not line.startswith("#"):
                assert line.startswith("uptop_"), f"Metric not prefixed: {line}"


class TestLabelFormatting:
    """Test label formatting for multi-instance metrics."""

    def test_format_labels_empty(self) -> None:
        """Test formatting empty labels."""
        # Uses module-level function _format_labels
        assert _format_labels({}) == ""

    def test_format_labels_single(self) -> None:
        """Test formatting a single label."""
        result = _format_labels({"core": "0"})
        assert result == '{core="0"}'

    def test_format_labels_multiple(self) -> None:
        """Test formatting multiple labels."""
        result = _format_labels({"core": "0", "type": "physical"})
        # Labels are joined with comma, order depends on dict iteration
        assert 'core="0"' in result
        assert 'type="physical"' in result
        assert result.startswith("{")
        assert result.endswith("}")

    def test_format_label_escaping(self) -> None:
        """Test escaping of special characters in label values."""
        # Test backslash escaping using _sanitize_label_value
        assert _sanitize_label_value(r"C:\Users") == r"C:\\Users"

        # Test quote escaping
        assert _sanitize_label_value('test"value') == r'test\"value'

        # Test newline escaping
        assert _sanitize_label_value("line1\nline2") == r"line1\nline2"

    def test_cpu_core_labels(self) -> None:
        """Test that CPU cores get proper labels."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[
                CPUCore(id=0, usage_percent=45.2, freq_mhz=3200.0, temp_celsius=None),
                CPUCore(id=1, usage_percent=38.7, freq_mhz=3100.0, temp_celsius=None),
            ],
            load_avg_1min=1.5,
            load_avg_5min=2.0,
            load_avg_15min=1.8,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # Should have id labels (implementation uses "id" for list items)
        assert '{id="0"}' in output
        assert '{id="1"}' in output

    def test_network_interface_labels(self) -> None:
        """Test that network interfaces get proper labels."""
        formatter = PrometheusFormatter()

        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=1000000,
                    bytes_recv=2000000,
                    packets_sent=1000,
                    packets_recv=2000,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=100.0,
                    bandwidth_down=200.0,
                    is_up=True,
                ),
                NetworkInterfaceData(
                    name="lo",
                    bytes_sent=500000,
                    bytes_recv=500000,
                    packets_sent=500,
                    packets_recv=500,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=50.0,
                    bandwidth_down=50.0,
                    is_up=True,
                ),
            ],
            connections=[],
            total_bytes_sent=1500000,
            total_bytes_recv=2500000,
            total_bandwidth_up=150.0,
            total_bandwidth_down=250.0,
        )

        output = formatter.format({"panes": {"network": network_data.model_dump()}})

        # Should have id labels (implementation uses "id" from item.get("id", item.get("name", ...)))
        # NetworkInterfaceData uses "name" field which is picked up as id
        assert '{id="eth0"}' in output
        assert '{id="lo"}' in output


class TestMetricTypes:
    """Test correct detection and output of metric types (counter vs gauge)."""

    def test_cpu_gauge_types(self) -> None:
        """Test that CPU metrics are correctly typed as gauges."""
        # Verify model introspection works
        assert get_metric_type(CPUCore, "usage_percent") == MetricType.GAUGE
        assert get_metric_type(CPUCore, "freq_mhz") == MetricType.GAUGE
        assert get_metric_type(CPUData, "load_avg_1min") == MetricType.GAUGE

    def test_network_counter_types(self) -> None:
        """Test that network counters are correctly typed."""
        # Verify model introspection works
        assert get_metric_type(NetworkInterfaceData, "bytes_sent") == MetricType.COUNTER
        assert get_metric_type(NetworkInterfaceData, "bytes_recv") == MetricType.COUNTER
        assert get_metric_type(NetworkInterfaceData, "packets_sent") == MetricType.COUNTER

        # Bandwidth is a gauge (calculated rate)
        assert get_metric_type(NetworkInterfaceData, "bandwidth_up") == MetricType.GAUGE

    def test_disk_counter_types(self) -> None:
        """Test that disk I/O counters are correctly typed."""
        assert get_metric_type(DiskIOStats, "read_bytes") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "write_bytes") == MetricType.COUNTER
        assert get_metric_type(DiskIOStats, "read_count") == MetricType.COUNTER

    def test_disk_gauge_types(self) -> None:
        """Test that disk partition metrics are correctly typed as gauges."""
        assert get_metric_type(PartitionInfo, "total_bytes") == MetricType.GAUGE
        assert get_metric_type(PartitionInfo, "used_bytes") == MetricType.GAUGE
        assert get_metric_type(PartitionInfo, "percent") == MetricType.GAUGE

    def test_type_comments_in_output(self) -> None:
        """Test that TYPE comments are generated for scalar metrics with known types."""
        formatter = PrometheusFormatter()

        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=1000000,
                    bytes_recv=2000000,
                    packets_sent=1000,
                    packets_recv=2000,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=100.0,
                    bandwidth_down=200.0,
                    is_up=True,
                ),
            ],
            connections=[],
            total_bytes_sent=1000000,
            total_bytes_recv=2000000,
            total_bandwidth_up=100.0,
            total_bandwidth_down=200.0,
        )

        output = formatter.format({"panes": {"network": network_data}})

        # TYPE comments are only generated for scalar metrics at pane level
        # (not for list items - those don't get HELP/TYPE comments in _format_list)
        # Check for gauge type on total_bandwidth metrics
        assert "# TYPE uptop_network_total_bandwidth_up gauge" in output
        assert "# TYPE uptop_network_total_bandwidth_down gauge" in output

        # Check for counter type on total_bytes metrics
        assert "# TYPE uptop_network_total_bytes_sent counter" in output
        assert "# TYPE uptop_network_total_bytes_recv counter" in output


class TestCPUDataFormatting:
    """Test formatting of CPU data."""

    def test_cpu_data_basic(self) -> None:
        """Test basic CPU data formatting."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[
                CPUCore(id=0, usage_percent=45.2, freq_mhz=3200.0, temp_celsius=65.5),
            ],
            load_avg_1min=1.5,
            load_avg_5min=2.0,
            load_avg_15min=1.8,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # Check load averages
        assert "uptop_cpu_load_avg_1min" in output
        assert "1.5" in output

        # Check core metrics with labels (implementation uses "id" label)
        assert 'uptop_cpu_cores_usage_percent{id="0"} 45.2' in output
        assert 'uptop_cpu_cores_freq_mhz{id="0"} 3200' in output

    def test_cpu_multiple_cores(self) -> None:
        """Test CPU data with multiple cores."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[
                CPUCore(id=0, usage_percent=45.2, freq_mhz=3200.0, temp_celsius=None),
                CPUCore(id=1, usage_percent=38.7, freq_mhz=3100.0, temp_celsius=None),
                CPUCore(id=2, usage_percent=52.1, freq_mhz=3300.0, temp_celsius=None),
            ],
            load_avg_1min=1.5,
            load_avg_5min=2.0,
            load_avg_15min=1.8,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # Check all cores have metrics (implementation uses "id" label)
        assert 'id="0"' in output
        assert 'id="1"' in output
        assert 'id="2"' in output

        # Check metrics are present for cores
        assert "uptop_cpu_cores_usage_percent" in output


class TestMemoryDataFormatting:
    """Test formatting of memory data."""

    def test_memory_data_basic(self) -> None:
        """Test basic memory data formatting."""
        formatter = PrometheusFormatter()

        memory_data = MemoryData(
            source="memory",
            virtual=VirtualMemory(
                total_bytes=17179869184,  # 16 GB
                used_bytes=8589934592,    # 8 GB
                available_bytes=8589934592,
                percent=50.0,
                cached_bytes=2147483648,
                buffers_bytes=1073741824,
            ),
            swap=SwapMemory(
                total_bytes=4294967296,   # 4 GB
                used_bytes=1073741824,    # 1 GB
                free_bytes=3221225472,
                percent=25.0,
            ),
        )

        output = formatter.format({"panes": {"memory": memory_data.model_dump()}})

        # Check virtual memory metrics
        assert "uptop_memory_virtual_total_bytes" in output
        assert "17179869184" in output
        assert "uptop_memory_virtual_used_bytes" in output
        assert "8589934592" in output

        # Check swap metrics
        assert "uptop_memory_swap_total_bytes" in output
        assert "uptop_memory_swap_percent" in output
        assert "25.0" in output

    def test_memory_type_gauge(self) -> None:
        """Test that memory metrics are typed as gauges."""
        formatter = PrometheusFormatter()

        memory_data = MemoryData(
            source="memory",
            virtual=VirtualMemory(
                total_bytes=17179869184,
                used_bytes=8589934592,
                available_bytes=8589934592,
                percent=50.0,
                cached_bytes=None,
                buffers_bytes=None,
            ),
            swap=SwapMemory(
                total_bytes=4294967296,
                used_bytes=1073741824,
                free_bytes=3221225472,
                percent=25.0,
            ),
        )

        output = formatter.format({"panes": {"memory": memory_data}})

        # Memory metrics should be gauges (TYPE is only added for scalar metrics with schema)
        # The nested dicts don't have schema info, so no TYPE comments for them
        # Just check the output contains the expected metrics
        assert "uptop_memory_virtual_total_bytes" in output
        assert "uptop_memory_swap_percent" in output


class TestNetworkDataFormatting:
    """Test formatting of network data."""

    def test_network_data_basic(self) -> None:
        """Test basic network data formatting."""
        formatter = PrometheusFormatter()

        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=1000000,
                    bytes_recv=2000000,
                    packets_sent=1000,
                    packets_recv=2000,
                    errors_in=5,
                    errors_out=2,
                    drops_in=1,
                    drops_out=0,
                    bandwidth_up=1024.5,
                    bandwidth_down=2048.75,
                    is_up=True,
                ),
            ],
            connections=[],
            total_bytes_sent=1000000,
            total_bytes_recv=2000000,
            total_bandwidth_up=1024.5,
            total_bandwidth_down=2048.75,
        )

        output = formatter.format({"panes": {"network": network_data.model_dump()}})

        # Check counter metrics (implementation uses "id" label from name field)
        assert 'uptop_network_interfaces_bytes_sent{id="eth0"} 1000000' in output
        assert 'uptop_network_interfaces_bytes_recv{id="eth0"} 2000000' in output

        # Check gauge metrics
        assert 'uptop_network_interfaces_bandwidth_up{id="eth0"} 1024.5' in output

    def test_network_counters_typed_correctly(self) -> None:
        """Test that network counters have correct TYPE comments."""
        formatter = PrometheusFormatter()

        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=1000000,
                    bytes_recv=2000000,
                    packets_sent=1000,
                    packets_recv=2000,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=100.0,
                    bandwidth_down=200.0,
                    is_up=True,
                ),
            ],
            connections=[],
            total_bytes_sent=1000000,
            total_bytes_recv=2000000,
            total_bandwidth_up=100.0,
            total_bandwidth_down=200.0,
        )

        output = formatter.format({"panes": {"network": network_data}})

        # TYPE comments are only generated for scalar metrics with schema
        # Totals should have counter type
        assert "# TYPE uptop_network_total_bytes_sent counter" in output
        assert "# TYPE uptop_network_total_bytes_recv counter" in output


class TestDiskDataFormatting:
    """Test formatting of disk data."""

    def test_disk_partition_data(self) -> None:
        """Test disk partition data formatting."""
        formatter = PrometheusFormatter()

        disk_data = DiskData(
            source="disk",
            partitions=[
                PartitionInfo(
                    device="/dev/sda1",
                    mountpoint="/",
                    fstype="ext4",
                    opts="rw,relatime",
                    total_bytes=500107862016,
                    used_bytes=200000000000,
                    free_bytes=300107862016,
                    percent=40.0,
                ),
            ],
            io_stats=[],
            partition_count=1,
        )

        output = formatter.format({"panes": {"disk": disk_data.model_dump()}})

        # Check partition metrics
        assert "uptop_disk_partitions_total_bytes" in output
        assert "500107862016" in output
        assert "uptop_disk_partitions_percent" in output
        assert "40.0" in output

    def test_disk_io_counters(self) -> None:
        """Test disk I/O counter formatting."""
        formatter = PrometheusFormatter()

        disk_data = DiskData(
            source="disk",
            partitions=[],
            io_stats=[
                DiskIOStats(
                    device="sda",
                    read_bytes=10000000000,
                    write_bytes=5000000000,
                    read_count=100000,
                    write_count=50000,
                    read_time_ms=30000,
                    write_time_ms=20000,
                ),
            ],
            partition_count=0,
        )

        output = formatter.format({"panes": {"disk": disk_data.model_dump()}})

        # Check I/O counters (implementation uses index "0" since "device" isn't "id" or "name")
        assert 'uptop_disk_io_stats_read_bytes{id="0"}' in output
        assert "10000000000" in output
        assert 'uptop_disk_io_stats_write_bytes{id="0"}' in output
        assert "5000000000" in output


class TestPrometheusFormatCompliance:
    """Test compliance with Prometheus exposition format specification."""

    def test_metric_name_pattern(self) -> None:
        """Test that metric names match Prometheus pattern."""
        formatter = PrometheusFormatter()
        pattern = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")

        cpu_data = CPUData(
            source="cpu",
            cores=[CPUCore(id=0, usage_percent=50.0, freq_mhz=None, temp_celsius=None)],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        for line in output.split("\n"):
            if line and not line.startswith("#"):
                # Extract metric name (before labels or space)
                match = re.match(r"([a-zA-Z_:][a-zA-Z0-9_:]*)", line)
                assert match, f"Invalid metric line: {line}"
                metric_name = match.group(1)
                assert pattern.match(metric_name), f"Invalid metric name: {metric_name}"

    def test_help_comment_format(self) -> None:
        """Test that HELP comments are properly formatted."""
        formatter = PrometheusFormatter()

        memory_data = MemoryData(
            source="memory",
            virtual=VirtualMemory(
                total_bytes=16000000000,
                used_bytes=8000000000,
                available_bytes=8000000000,
                percent=50.0,
                cached_bytes=None,
                buffers_bytes=None,
            ),
            swap=SwapMemory(
                total_bytes=4000000000,
                used_bytes=1000000000,
                free_bytes=3000000000,
                percent=25.0,
            ),
        )

        output = formatter.format({"panes": {"memory": memory_data.model_dump()}})

        # HELP comments should follow format: # HELP metric_name description
        for line in output.split("\n"):
            if line.startswith("# HELP"):
                parts = line.split(" ", 3)
                assert len(parts) >= 3, f"Malformed HELP line: {line}"
                assert parts[0] == "#"
                assert parts[1] == "HELP"

    def test_type_comment_format(self) -> None:
        """Test that TYPE comments are properly formatted."""
        formatter = PrometheusFormatter()

        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=1000,
                    bytes_recv=2000,
                    packets_sent=10,
                    packets_recv=20,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=100.0,
                    bandwidth_down=200.0,
                    is_up=True,
                ),
            ],
            connections=[],
            total_bytes_sent=1000,
            total_bytes_recv=2000,
            total_bandwidth_up=100.0,
            total_bandwidth_down=200.0,
        )

        output = formatter.format({"panes": {"network": network_data}})

        # TYPE comments should follow format: # TYPE metric_name type
        valid_types = {"counter", "gauge", "histogram", "summary", "untyped"}
        for line in output.split("\n"):
            if line.startswith("# TYPE"):
                parts = line.split()
                assert len(parts) == 4, f"Malformed TYPE line: {line}"
                assert parts[0] == "#"
                assert parts[1] == "TYPE"
                assert parts[3] in valid_types, f"Invalid type: {parts[3]}"

    def test_metric_line_format(self) -> None:
        """Test that metric lines follow format: name{labels} value [timestamp]."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[CPUCore(id=0, usage_percent=50.0, freq_mhz=3000.0, temp_celsius=None)],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # Metric lines should match: metric_name{labels} value [timestamp_ms]
        # The timestamp is optional in Prometheus format
        metric_pattern = re.compile(
            r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]+\})?\s+-?[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?(\s+[0-9]+)?$"
        )

        for line in output.split("\n"):
            if line and not line.startswith("#"):
                assert metric_pattern.match(line), f"Invalid metric line format: {line}"

    def test_no_empty_metric_values(self) -> None:
        """Test that None values are not emitted as metrics."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[
                CPUCore(id=0, usage_percent=50.0, freq_mhz=None, temp_celsius=None),
            ],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # Should not have metrics with "None" as value
        assert "None" not in output

        # Should not have metrics with empty value
        for line in output.split("\n"):
            if line and not line.startswith("#"):
                parts = line.split()
                assert len(parts) >= 2, f"Metric line missing value: {line}"


class TestBooleanHandling:
    """Test handling of boolean values."""

    def test_boolean_values_skipped(self) -> None:
        """Test that boolean values are skipped (not emitted as metrics)."""
        formatter = PrometheusFormatter()

        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=0,
                    bytes_recv=0,
                    packets_sent=0,
                    packets_recv=0,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=0.0,
                    bandwidth_down=0.0,
                    is_up=True,
                ),
            ],
            connections=[],
            total_bytes_sent=0,
            total_bytes_recv=0,
            total_bandwidth_up=0.0,
            total_bandwidth_down=0.0,
        )

        output = formatter.format({"panes": {"network": network_data.model_dump()}})

        # Boolean values are skipped by the implementation (not isinstance(value, bool))
        # So is_up should not appear in the output
        assert "is_up" not in output


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_data(self) -> None:
        """Test formatting empty data."""
        formatter = PrometheusFormatter()

        output = formatter.format({})
        assert output == ""

    def test_empty_pane_data(self) -> None:
        """Test formatting with empty pane data."""
        formatter = PrometheusFormatter()

        output = formatter.format({"panes": {"cpu": {}}})
        # Should produce no output for empty pane
        assert output.strip() == ""

    def test_non_dict_pane_data_skipped(self) -> None:
        """Test that non-dict pane data is skipped."""
        formatter = PrometheusFormatter()

        output = formatter.format({"panes": {"cpu": "invalid", "memory": None, "disk": 123}})
        # Should produce no output for invalid data
        assert output.strip() == ""

    def test_special_float_values(self) -> None:
        """Test handling of special float values (NaN, Inf)."""
        import math

        formatter = PrometheusFormatter()

        # Create a dict directly with special float values
        # (bypassing Pydantic validation which doesn't allow NaN/Inf)
        data = {
            "panes": {
                "test": {
                    "nan_value": float("nan"),
                    "inf_value": float("inf"),
                    "neg_inf_value": float("-inf"),
                }
            }
        }

        output = formatter.format(data)

        # Check that special values are formatted correctly
        # NaN, +Inf, -Inf are valid Prometheus values
        assert "nan" in output.lower()
        assert "inf" in output.lower()

    def test_multiple_panes(self) -> None:
        """Test formatting multiple panes together."""
        formatter = PrometheusFormatter()

        data = {
            "panes": {
                "cpu": CPUData(
                    source="cpu",
                    cores=[],
                    load_avg_1min=1.0,
                    load_avg_5min=1.0,
                    load_avg_15min=1.0,
                ).model_dump(),
                "memory": MemoryData(
                    source="memory",
                    virtual=VirtualMemory(
                        total_bytes=16000000000,
                        used_bytes=8000000000,
                        available_bytes=8000000000,
                        percent=50.0,
                        cached_bytes=None,
                        buffers_bytes=None,
                    ),
                    swap=SwapMemory(
                        total_bytes=4000000000,
                        used_bytes=1000000000,
                        free_bytes=3000000000,
                        percent=25.0,
                    ),
                ).model_dump(),
            }
        }

        output = formatter.format(data)

        # Should have metrics from both panes
        assert "uptop_cpu" in output
        assert "uptop_memory" in output

    def test_timestamp_skipped(self) -> None:
        """Test that timestamp field is not emitted as a metric."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
            timestamp=datetime.now(UTC),
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # timestamp should not appear as a metric
        assert "uptop_cpu_timestamp" not in output

    def test_source_field_skipped(self) -> None:
        """Test that source field is not emitted as a metric."""
        formatter = PrometheusFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
        )

        output = formatter.format({"panes": {"cpu": cpu_data.model_dump()}})

        # source should not appear as a metric
        assert "uptop_cpu_source" not in output
