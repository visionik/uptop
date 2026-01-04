"""Tests for JSON Formatter Plugin.

This module tests the JsonFormatter class from uptop.formatters.json_formatter.
Tests cover:
- Formatting single pane data
- Formatting multiple panes
- Pretty print vs compact output
- Integration with real data models (CPUData, MemoryData, etc.)
- Datetime serialization in ISO format
- Timestamp inclusion in output
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from uptop.formatters import JsonFormatter
from uptop.formatters.json_formatter import JsonFormatter as JsonFormatterDirect
from uptop.models.base import MetricData, PluginType
from uptop.plugin_api.base import FormatterPlugin


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class TestJsonFormatterBasics:
    """Tests for basic JsonFormatter functionality."""

    def test_formatter_inherits_from_formatter_plugin(self) -> None:
        """Test that JsonFormatter inherits from FormatterPlugin."""
        assert issubclass(JsonFormatter, FormatterPlugin)

    def test_formatter_class_attributes(self) -> None:
        """Test that class attributes are set correctly."""
        assert JsonFormatter.name == "json"
        assert JsonFormatter.format_name == "JSON"
        assert JsonFormatter.file_extension == ".json"
        assert JsonFormatter.cli_flag == "--json"

    def test_formatter_plugin_type(self) -> None:
        """Test that get_plugin_type returns FORMATTER."""
        assert JsonFormatter.get_plugin_type() == PluginType.FORMATTER

    def test_default_pretty_print_is_true(self) -> None:
        """Test that pretty_print defaults to True."""
        formatter = JsonFormatter()
        assert formatter.pretty_print is True

    def test_pretty_print_can_be_set_false(self) -> None:
        """Test that pretty_print can be set to False."""
        formatter = JsonFormatter(pretty_print=False)
        assert formatter.pretty_print is False

    def test_initialize_with_config(self) -> None:
        """Test that initialize() can set pretty_print from config."""
        formatter = JsonFormatter()
        formatter.initialize({"pretty_print": False})
        assert formatter.pretty_print is False

    def test_initialize_without_config(self) -> None:
        """Test that initialize() without config preserves default."""
        formatter = JsonFormatter(pretty_print=True)
        formatter.initialize(None)
        assert formatter.pretty_print is True


class TestJsonFormatterOutput:
    """Tests for JsonFormatter output format."""

    def test_format_empty_panes(self) -> None:
        """Test formatting with empty panes dict."""
        formatter = JsonFormatter()
        result = formatter.format({"panes": {}})

        parsed = json.loads(result)
        assert "timestamp" in parsed
        assert "panes" in parsed
        assert parsed["panes"] == {}

    def test_format_includes_timestamp(self) -> None:
        """Test that output includes a timestamp."""
        formatter = JsonFormatter()
        result = formatter.format({"panes": {}})

        parsed = json.loads(result)
        assert "timestamp" in parsed
        # Should be a valid ISO format timestamp
        timestamp = datetime.fromisoformat(parsed["timestamp"])
        assert timestamp is not None

    def test_format_preserves_custom_timestamp(self) -> None:
        """Test that a provided timestamp is preserved."""
        formatter = JsonFormatter()
        custom_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = formatter.format({"panes": {}, "timestamp": custom_time})

        parsed = json.loads(result)
        assert parsed["timestamp"] == "2024-01-15T10:30:00+00:00"

    def test_format_includes_hostname(self) -> None:
        """Test that hostname is included when provided."""
        formatter = JsonFormatter()
        result = formatter.format({"panes": {}, "hostname": "testhost"})

        parsed = json.loads(result)
        assert parsed["hostname"] == "testhost"

    def test_format_valid_json_output(self) -> None:
        """Test that output is valid JSON."""
        formatter = JsonFormatter()
        result = formatter.format({"panes": {}})

        # Should not raise
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


class TestJsonFormatterPrettyPrint:
    """Tests for pretty print vs compact output."""

    def test_pretty_print_has_indentation(self) -> None:
        """Test that pretty_print=True produces indented output."""
        formatter = JsonFormatter(pretty_print=True)
        result = formatter.format({"panes": {}, "hostname": "test"})

        # Pretty print should have newlines and spaces
        assert "\n" in result
        assert "  " in result  # Two-space indent

    def test_compact_output_no_indentation(self) -> None:
        """Test that pretty_print=False produces compact output."""
        formatter = JsonFormatter(pretty_print=False)
        result = formatter.format({"panes": {}, "hostname": "test"})

        # Compact output should not have newlines (except possibly in values)
        assert "\n" not in result
        # Compact uses no spaces after separators
        assert ": " not in result

    def test_compact_output_single_line(self) -> None:
        """Test that compact output is a single line."""
        formatter = JsonFormatter(pretty_print=False)
        result = formatter.format({"panes": {}, "hostname": "test"})

        lines = result.strip().split("\n")
        assert len(lines) == 1

    def test_both_formats_parse_identically(self) -> None:
        """Test that pretty and compact produce identical data."""
        data = {"panes": {}, "hostname": "test", "timestamp": _utcnow()}

        pretty_formatter = JsonFormatter(pretty_print=True)
        compact_formatter = JsonFormatter(pretty_print=False)

        pretty_result = json.loads(pretty_formatter.format(data))
        compact_result = json.loads(compact_formatter.format(data))

        assert pretty_result == compact_result


class TestJsonFormatterWithMetricData:
    """Tests for formatting MetricData instances."""

    def test_format_single_metric_data(self) -> None:
        """Test formatting a single MetricData instance."""
        formatter = JsonFormatter()
        metric = MetricData(source="test")
        result = formatter.format({"panes": {"test": metric}})

        parsed = json.loads(result)
        assert "panes" in parsed
        assert "test" in parsed["panes"]
        pane_data = parsed["panes"]["test"]
        assert pane_data["source"] == "test"
        assert "timestamp" in pane_data

    def test_format_multiple_metric_data(self) -> None:
        """Test formatting multiple MetricData instances."""
        formatter = JsonFormatter()
        metrics = {
            "pane1": MetricData(source="source1"),
            "pane2": MetricData(source="source2"),
            "pane3": MetricData(source="source3"),
        }
        result = formatter.format({"panes": metrics})

        parsed = json.loads(result)
        assert len(parsed["panes"]) == 3
        assert parsed["panes"]["pane1"]["source"] == "source1"
        assert parsed["panes"]["pane2"]["source"] == "source2"
        assert parsed["panes"]["pane3"]["source"] == "source3"

    def test_metric_data_timestamp_serialized_as_iso(self) -> None:
        """Test that MetricData timestamps are serialized as ISO strings."""
        formatter = JsonFormatter()
        timestamp = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        metric = MetricData(source="test", timestamp=timestamp)
        result = formatter.format({"panes": {"test": metric}})

        parsed = json.loads(result)
        pane_timestamp = parsed["panes"]["test"]["timestamp"]
        # Should be a string, not a dict or other object
        assert isinstance(pane_timestamp, str)
        # Should parse back to a datetime
        parsed_dt = datetime.fromisoformat(pane_timestamp)
        assert parsed_dt.year == 2024
        assert parsed_dt.month == 6
        assert parsed_dt.day == 15


class TestJsonFormatterWithRealModels:
    """Tests using real uptop data models (CPUData, MemoryData, etc.)."""

    def test_format_cpu_data(self) -> None:
        """Test formatting CPUData model."""
        from uptop.plugins.cpu import CPUCore, CPUData

        formatter = JsonFormatter()
        cpu_data = CPUData(
            source="cpu",
            cores=[
                CPUCore(id=0, usage_percent=25.5, freq_mhz=2400.0),
                CPUCore(id=1, usage_percent=30.2, freq_mhz=2400.0),
            ],
            load_avg_1min=1.5,
            load_avg_5min=1.2,
            load_avg_15min=0.9,
        )
        result = formatter.format({"panes": {"cpu": cpu_data}})

        parsed = json.loads(result)
        cpu = parsed["panes"]["cpu"]

        assert cpu["source"] == "cpu"
        assert len(cpu["cores"]) == 2
        assert cpu["cores"][0]["id"] == 0
        assert cpu["cores"][0]["usage_percent"] == 25.5
        assert cpu["cores"][0]["freq_mhz"] == 2400.0
        assert cpu["load_avg_1min"] == 1.5

    def test_format_memory_data(self) -> None:
        """Test formatting MemoryData model."""
        from uptop.plugins.memory import MemoryData, SwapMemory, VirtualMemory

        formatter = JsonFormatter()
        memory_data = MemoryData(
            source="memory",
            virtual=VirtualMemory(
                total_bytes=16_000_000_000,
                used_bytes=8_000_000_000,
                available_bytes=8_000_000_000,
                percent=50.0,
            ),
            swap=SwapMemory(
                total_bytes=4_000_000_000,
                used_bytes=1_000_000_000,
                free_bytes=3_000_000_000,
                percent=25.0,
            ),
        )
        result = formatter.format({"panes": {"memory": memory_data}})

        parsed = json.loads(result)
        memory = parsed["panes"]["memory"]

        assert memory["source"] == "memory"
        assert memory["virtual"]["total_bytes"] == 16_000_000_000
        assert memory["virtual"]["percent"] == 50.0
        assert memory["swap"]["total_bytes"] == 4_000_000_000

    def test_format_disk_data(self) -> None:
        """Test formatting DiskData model."""
        from uptop.plugins.disk import DiskData, DiskIOStats, PartitionInfo

        formatter = JsonFormatter()
        disk_data = DiskData(
            source="disk",
            partitions=[
                PartitionInfo(
                    device="/dev/sda1",
                    mountpoint="/",
                    fstype="ext4",
                    total_bytes=500_000_000_000,
                    used_bytes=200_000_000_000,
                    free_bytes=300_000_000_000,
                    percent=40.0,
                ),
            ],
            io_stats=[
                DiskIOStats(
                    device="sda",
                    read_bytes=1_000_000_000,
                    write_bytes=500_000_000,
                    read_count=100_000,
                    write_count=50_000,
                    read_time_ms=5000,
                    write_time_ms=3000,
                ),
            ],
            partition_count=1,
        )
        result = formatter.format({"panes": {"disk": disk_data}})

        parsed = json.loads(result)
        disk = parsed["panes"]["disk"]

        assert disk["source"] == "disk"
        assert len(disk["partitions"]) == 1
        assert disk["partitions"][0]["device"] == "/dev/sda1"
        assert disk["partitions"][0]["percent"] == 40.0
        assert len(disk["io_stats"]) == 1
        assert disk["io_stats"][0]["read_bytes"] == 1_000_000_000

    def test_format_network_data(self) -> None:
        """Test formatting NetworkData model."""
        from uptop.plugins.network import NetworkData, NetworkInterfaceData

        formatter = JsonFormatter()
        network_data = NetworkData(
            source="network",
            interfaces=[
                NetworkInterfaceData(
                    name="eth0",
                    bytes_sent=1_000_000,
                    bytes_recv=2_000_000,
                    packets_sent=10_000,
                    packets_recv=20_000,
                    errors_in=0,
                    errors_out=0,
                    drops_in=0,
                    drops_out=0,
                    bandwidth_up=10_000.0,
                    bandwidth_down=20_000.0,
                    is_up=True,
                ),
            ],
            total_bytes_sent=1_000_000,
            total_bytes_recv=2_000_000,
            total_bandwidth_up=10_000.0,
            total_bandwidth_down=20_000.0,
        )
        result = formatter.format({"panes": {"network": network_data}})

        parsed = json.loads(result)
        network = parsed["panes"]["network"]

        assert network["source"] == "network"
        assert len(network["interfaces"]) == 1
        assert network["interfaces"][0]["name"] == "eth0"
        assert network["interfaces"][0]["bytes_sent"] == 1_000_000
        assert network["total_bandwidth_up"] == 10_000.0

    def test_format_multiple_real_panes(self) -> None:
        """Test formatting multiple real pane data models together."""
        from uptop.plugins.cpu import CPUCore, CPUData
        from uptop.plugins.memory import MemoryData, SwapMemory, VirtualMemory

        formatter = JsonFormatter()

        cpu_data = CPUData(
            source="cpu",
            cores=[CPUCore(id=0, usage_percent=50.0)],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
        )
        memory_data = MemoryData(
            source="memory",
            virtual=VirtualMemory(
                total_bytes=16_000_000_000,
                used_bytes=8_000_000_000,
                available_bytes=8_000_000_000,
                percent=50.0,
            ),
            swap=SwapMemory(
                total_bytes=4_000_000_000,
                used_bytes=0,
                free_bytes=4_000_000_000,
                percent=0.0,
            ),
        )

        result = formatter.format({
            "panes": {"cpu": cpu_data, "memory": memory_data},
            "hostname": "testhost",
        })

        parsed = json.loads(result)

        assert parsed["hostname"] == "testhost"
        assert "cpu" in parsed["panes"]
        assert "memory" in parsed["panes"]
        assert parsed["panes"]["cpu"]["source"] == "cpu"
        assert parsed["panes"]["memory"]["source"] == "memory"


class TestJsonFormatterConvenienceMethods:
    """Tests for convenience methods."""

    def test_format_panes_method(self) -> None:
        """Test the format_panes convenience method."""
        formatter = JsonFormatter()
        panes = {
            "test1": MetricData(source="test1"),
            "test2": MetricData(source="test2"),
        }
        result = formatter.format_panes(panes)

        parsed = json.loads(result)
        assert "panes" in parsed
        assert len(parsed["panes"]) == 2
        assert parsed["panes"]["test1"]["source"] == "test1"

    def test_get_ai_help_docs_returns_markdown(self) -> None:
        """Test that get_ai_help_docs returns markdown documentation."""
        formatter = JsonFormatter()
        docs = formatter.get_ai_help_docs()

        assert isinstance(docs, str)
        assert "## JSON Formatter" in docs
        assert "pretty_print" in docs


class TestJsonFormatterEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_format_with_none_values(self) -> None:
        """Test formatting data with None values."""
        from uptop.plugins.cpu import CPUCore, CPUData

        formatter = JsonFormatter()
        cpu_data = CPUData(
            source="cpu",
            cores=[
                CPUCore(id=0, usage_percent=50.0, freq_mhz=None, temp_celsius=None),
            ],
            load_avg_1min=1.0,
            load_avg_5min=1.0,
            load_avg_15min=1.0,
        )
        result = formatter.format({"panes": {"cpu": cpu_data}})

        parsed = json.loads(result)
        core = parsed["panes"]["cpu"]["cores"][0]
        assert core["freq_mhz"] is None
        assert core["temp_celsius"] is None

    def test_format_with_dict_pane_data(self) -> None:
        """Test that already-serialized dict data is preserved."""
        formatter = JsonFormatter()
        pane_dict = {"source": "test", "value": 42}
        result = formatter.format({"panes": {"test": pane_dict}})

        parsed = json.loads(result)
        assert parsed["panes"]["test"]["source"] == "test"
        assert parsed["panes"]["test"]["value"] == 42

    def test_format_preserves_extra_top_level_keys(self) -> None:
        """Test that extra keys at top level are preserved."""
        formatter = JsonFormatter()
        result = formatter.format({
            "panes": {},
            "custom_key": "custom_value",
            "another_key": 123,
        })

        parsed = json.loads(result)
        assert parsed["custom_key"] == "custom_value"
        assert parsed["another_key"] == 123

    def test_format_handles_unicode(self) -> None:
        """Test that unicode characters are handled correctly."""
        formatter = JsonFormatter()
        result = formatter.format({
            "panes": {},
            "hostname": "host-with-unicode-\u00e9\u00e8\u00ea",
        })

        parsed = json.loads(result)
        assert parsed["hostname"] == "host-with-unicode-\u00e9\u00e8\u00ea"

    def test_import_from_formatters_package(self) -> None:
        """Test that JsonFormatter can be imported from formatters package."""
        from uptop.formatters import JsonFormatter as ImportedFormatter

        assert ImportedFormatter is JsonFormatterDirect


class TestJsonFormatterMetadata:
    """Tests for formatter metadata."""

    def test_get_metadata_returns_correct_info(self) -> None:
        """Test that get_metadata returns correct plugin metadata."""
        metadata = JsonFormatter.get_metadata()

        assert metadata.name == "json"
        assert metadata.display_name == "JSON Formatter"
        assert metadata.plugin_type == PluginType.FORMATTER
        assert metadata.version == "0.1.0"
