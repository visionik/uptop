"""Tests for uptop CLI modes (--once, --json, --prometheus, --panes).

This module tests the CLI mode functionality including:
- --once flag for single snapshot collection
- --json output format
- --prometheus output format  
- --panes for filtering specific panes
- Invalid pane name handling
- Default behavior (--once when not TTY)
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from uptop.cli import app, parse_panes_option
from uptop.cli_runner import (
    build_snapshot,
    collect_all_panes,
    get_available_panes,
    get_formatter,
    run_cli_mode,
    run_cli_once,
    validate_pane_names,
)
from uptop.config import Config, load_config
from uptop.formatters import JsonFormatter, PrometheusFormatter
from uptop.models.base import MetricData

runner = CliRunner()


# ============================================================================
# Tests for parse_panes_option
# ============================================================================


class TestParsePanesOption:
    """Tests for the parse_panes_option function."""

    def test_none_input(self) -> None:
        """Test None input returns None."""
        assert parse_panes_option(None) is None

    def test_empty_list(self) -> None:
        """Test empty list returns None."""
        assert parse_panes_option([]) is None

    def test_single_pane(self) -> None:
        """Test single pane name."""
        result = parse_panes_option(["cpu"])
        assert result == ["cpu"]

    def test_multiple_panes(self) -> None:
        """Test multiple pane names from repeated flags."""
        result = parse_panes_option(["cpu", "memory"])
        assert result == ["cpu", "memory"]

    def test_comma_separated(self) -> None:
        """Test comma-separated pane names."""
        result = parse_panes_option(["cpu,memory,disk"])
        assert result == ["cpu", "memory", "disk"]

    def test_mixed_format(self) -> None:
        """Test mixed repeated and comma-separated."""
        result = parse_panes_option(["cpu,memory", "disk"])
        assert result == ["cpu", "memory", "disk"]

    def test_whitespace_handling(self) -> None:
        """Test whitespace is stripped."""
        result = parse_panes_option(["  cpu , memory  "])
        assert result == ["cpu", "memory"]


# ============================================================================
# Tests for validate_pane_names
# ============================================================================


class TestValidatePaneNames:
    """Tests for pane name validation."""

    def test_valid_pane_names(self) -> None:
        """Test valid pane names are accepted."""
        valid, invalid = validate_pane_names(["cpu", "memory", "disk"])
        assert valid == ["cpu", "memory", "disk"]
        assert invalid == []

    def test_invalid_pane_names(self) -> None:
        """Test invalid pane names are detected."""
        valid, invalid = validate_pane_names(["cpu", "invalid_pane"])
        assert valid == ["cpu"]
        assert invalid == ["invalid_pane"]

    def test_alias_resolution(self) -> None:
        """Test common aliases are resolved."""
        valid, invalid = validate_pane_names(["mem", "proc", "net"])
        assert "memory" in valid
        assert "processes" in valid
        assert "network" in valid
        assert invalid == []

    def test_case_insensitive(self) -> None:
        """Test pane names are case insensitive."""
        valid, invalid = validate_pane_names(["CPU", "Memory"])
        assert "cpu" in valid
        assert "memory" in valid


# ============================================================================
# Tests for get_available_panes
# ============================================================================


class TestGetAvailablePanes:
    """Tests for getting available panes."""

    def test_returns_list(self) -> None:
        """Test returns a list of pane names."""
        panes = get_available_panes()
        assert isinstance(panes, list)
        assert len(panes) > 0

    def test_contains_builtin_panes(self) -> None:
        """Test contains all built-in panes."""
        panes = get_available_panes()
        assert "cpu" in panes
        assert "memory" in panes
        assert "disk" in panes
        assert "network" in panes
        assert "processes" in panes


# ============================================================================
# Tests for get_formatter
# ============================================================================


class TestGetFormatter:
    """Tests for formatter retrieval."""

    def test_json_formatter(self) -> None:
        """Test JSON formatter is returned."""
        config = load_config()
        formatter = get_formatter("json", config)
        assert isinstance(formatter, JsonFormatter)

    def test_prometheus_formatter(self) -> None:
        """Test Prometheus formatter is returned."""
        config = load_config()
        formatter = get_formatter("prometheus", config)
        assert isinstance(formatter, PrometheusFormatter)

    def test_unknown_format_raises(self) -> None:
        """Test unknown format raises ValueError."""
        config = load_config()
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("unknown", config)


# ============================================================================
# Tests for build_snapshot
# ============================================================================


class TestBuildSnapshot:
    """Tests for snapshot building."""

    def test_basic_snapshot(self) -> None:
        """Test basic snapshot structure."""
        pane_data: dict[str, MetricData] = {}
        snapshot = build_snapshot(pane_data)

        assert "timestamp" in snapshot
        assert "hostname" in snapshot
        assert "panes" in snapshot
        assert isinstance(snapshot["panes"], dict)

    def test_with_pane_data(self) -> None:
        """Test snapshot with pane data."""

        class TestData(MetricData):
            value: int = 42

        pane_data = {"test": TestData()}
        snapshot = build_snapshot(pane_data)

        assert "test" in snapshot["panes"]


# ============================================================================
# Tests for collect_all_panes (async)
# ============================================================================


class TestCollectAllPanes:
    """Tests for async pane data collection."""

    @pytest.mark.asyncio
    async def test_collect_single_pane(self) -> None:
        """Test collecting data from a single pane."""
        data = await collect_all_panes(["cpu"])
        assert "cpu" in data
        assert data["cpu"] is not None

    @pytest.mark.asyncio
    async def test_collect_multiple_panes(self) -> None:
        """Test collecting data from multiple panes."""
        data = await collect_all_panes(["cpu", "memory"])
        assert "cpu" in data
        assert "memory" in data

    @pytest.mark.asyncio
    async def test_collect_all_default(self) -> None:
        """Test collecting from all panes when None specified."""
        data = await collect_all_panes(None)
        # Should have at least cpu and memory
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_invalid_pane_skipped(self) -> None:
        """Test invalid pane names are skipped."""
        data = await collect_all_panes(["cpu", "nonexistent"])
        # nonexistent should be silently skipped
        assert "cpu" in data
        assert "nonexistent" not in data


# ============================================================================
# Tests for run_cli_once (async)
# ============================================================================


class TestRunCliOnce:
    """Tests for single CLI run."""

    @pytest.mark.asyncio
    async def test_json_output(self) -> None:
        """Test JSON output is produced."""
        config = load_config()
        # Capture stdout
        with patch("builtins.print") as mock_print:
            exit_code = await run_cli_once("json", ["cpu"], config)

        assert exit_code == 0
        # Verify print was called with JSON
        assert mock_print.called
        output = mock_print.call_args[0][0]
        # Validate it's JSON
        parsed = json.loads(output)
        assert "panes" in parsed
        assert "cpu" in parsed["panes"]

    @pytest.mark.asyncio
    async def test_prometheus_output(self) -> None:
        """Test Prometheus output is produced."""
        config = load_config()
        with patch("builtins.print") as mock_print:
            exit_code = await run_cli_once("prometheus", ["cpu"], config)

        assert exit_code == 0
        assert mock_print.called
        output = mock_print.call_args[0][0]
        # Prometheus format should contain metric lines
        assert "uptop_cpu" in output

    @pytest.mark.asyncio
    async def test_invalid_pane_error(self) -> None:
        """Test error on invalid pane name."""
        config = load_config()
        exit_code = await run_cli_once("json", ["invalid_pane"], config)
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_invalid_format_error(self) -> None:
        """Test error on invalid format."""
        config = load_config()
        exit_code = await run_cli_once("invalid_format", ["cpu"], config)
        assert exit_code == 1


# ============================================================================
# Tests for run_cli_mode (sync wrapper)
# ============================================================================


class TestRunCliMode:
    """Tests for the synchronous CLI mode runner."""

    def test_once_mode(self) -> None:
        """Test once mode runs successfully."""
        config = load_config()
        with patch("builtins.print"):
            exit_code = run_cli_mode("json", ["cpu"], once=True, config=config)
        assert exit_code == 0

    def test_streaming_not_implemented(self) -> None:
        """Test streaming mode returns error."""
        config = load_config()
        exit_code = run_cli_mode("json", ["cpu"], once=False, config=config)
        assert exit_code == 1


# ============================================================================
# Tests for CLI commands using CliRunner
# ============================================================================


class TestCliOnceFlag:
    """Tests for --once flag via CLI."""

    def test_json_once(self) -> None:
        """Test --json --once produces valid JSON."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        assert result.exit_code == 0
        # Parse the output as JSON
        output = result.stdout
        parsed = json.loads(output)
        assert "panes" in parsed

    def test_once_exits_immediately(self) -> None:
        """Test --once flag causes immediate exit."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        assert result.exit_code == 0
        # Output should be complete JSON
        assert result.stdout.strip().endswith("}")


class TestCliJsonOutput:
    """Tests for --json output format."""

    def test_json_valid(self) -> None:
        """Test JSON output is valid."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        assert result.exit_code == 0
        # Should be valid JSON
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, dict)

    def test_json_has_timestamp(self) -> None:
        """Test JSON output includes timestamp."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        parsed = json.loads(result.stdout)
        assert "timestamp" in parsed

    def test_json_has_hostname(self) -> None:
        """Test JSON output includes hostname."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        parsed = json.loads(result.stdout)
        assert "hostname" in parsed

    def test_json_has_panes(self) -> None:
        """Test JSON output includes panes data."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu,memory"])
        parsed = json.loads(result.stdout)
        assert "panes" in parsed
        assert "cpu" in parsed["panes"]
        assert "memory" in parsed["panes"]


class TestCliPrometheusOutput:
    """Tests for --prometheus output format."""

    def test_prometheus_format(self) -> None:
        """Test Prometheus output format is valid."""
        result = runner.invoke(app, ["--prometheus", "--once", "--panes", "cpu"])
        assert result.exit_code == 0
        output = result.stdout
        # Should have Prometheus metric lines
        assert "uptop_cpu" in output

    def test_prometheus_has_labels(self) -> None:
        """Test Prometheus output includes labels."""
        result = runner.invoke(app, ["--prometheus", "--once", "--panes", "cpu"])
        output = result.stdout
        # Should have host label
        assert "host=" in output

    def test_prometheus_numeric_values(self) -> None:
        """Test Prometheus output has numeric values."""
        result = runner.invoke(app, ["--prometheus", "--once", "--panes", "cpu"])
        output = result.stdout
        # Each line should end with a number (possibly with timestamp)
        lines = [l for l in output.strip().split("\n") if not l.startswith("#")]
        for line in lines:
            if line.strip():
                # Line format: metric_name{labels} value [timestamp]
                parts = line.split()
                assert len(parts) >= 2
                # The value should be parseable as float
                value = parts[1] if len(parts) >= 2 else parts[0].split("}")[1]
                float(value)  # This will raise if not numeric


class TestCliPanesOption:
    """Tests for --panes option."""

    def test_single_pane(self) -> None:
        """Test selecting single pane."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "cpu" in parsed["panes"]
        # Should only have CPU
        assert len(parsed["panes"]) == 1

    def test_multiple_panes_comma(self) -> None:
        """Test comma-separated panes."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu,memory"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "cpu" in parsed["panes"]
        assert "memory" in parsed["panes"]

    def test_invalid_pane_error(self) -> None:
        """Test invalid pane name produces error."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "invalid_pane"])
        assert result.exit_code == 1
        assert "Unknown pane" in result.stderr or "Unknown pane" in result.stdout

    def test_invalid_pane_shows_available(self) -> None:
        """Test invalid pane error shows available panes."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "bad"])
        assert result.exit_code == 1
        output = result.stderr + result.stdout
        assert "cpu" in output.lower() or "memory" in output.lower()


class TestDefaultBehavior:
    """Tests for default CLI behavior."""

    def test_non_tty_uses_once(self) -> None:
        """Test non-TTY defaults to --once mode."""
        # CliRunner simulates non-TTY by default
        with patch.object(sys.stdin, "isatty", return_value=False):
            result = runner.invoke(app, ["--json", "--panes", "cpu"])
        assert result.exit_code == 0
        # Should produce output (--once behavior)
        assert result.stdout.strip() != ""

    def test_format_flag_implies_cli_mode(self) -> None:
        """Test format flags imply CLI mode."""
        result = runner.invoke(app, ["--json", "--panes", "cpu"])
        # Should run in CLI mode and produce JSON output
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "panes" in parsed


class TestCliCommand:
    """Tests for explicit 'cli' subcommand."""

    def test_cli_subcommand(self) -> None:
        """Test 'cli' subcommand works."""
        result = runner.invoke(app, ["cli", "--json", "--panes", "cpu"])
        assert result.exit_code == 0

    def test_cli_subcommand_once(self) -> None:
        """Test 'cli --once' works."""
        result = runner.invoke(app, ["cli", "--once", "--json", "--panes", "cpu"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "panes" in parsed


# ============================================================================
# Formatter Tests
# ============================================================================


class TestJsonFormatterOutput:
    """Tests for JSON formatter output."""

    def test_format_empty_panes(self) -> None:
        """Test formatting with no panes."""
        formatter = JsonFormatter()
        formatter.initialize()
        output = formatter.format({"panes": {}})
        parsed = json.loads(output)
        assert parsed["panes"] == {}

    def test_format_with_data(self) -> None:
        """Test formatting with pane data."""

        class TestData(MetricData):
            value: int = 42

        formatter = JsonFormatter()
        formatter.initialize()
        output = formatter.format({"panes": {"test": TestData()}})
        parsed = json.loads(output)
        assert parsed["panes"]["test"]["value"] == 42

    def test_pretty_print_on(self) -> None:
        """Test pretty printing is enabled by default."""
        formatter = JsonFormatter()
        formatter.initialize()
        output = formatter.format({"panes": {"test": {}}})
        # Pretty print has newlines
        assert "\n" in output

    def test_pretty_print_off(self) -> None:
        """Test compact output when pretty_print=False."""
        formatter = JsonFormatter(pretty_print=False)
        formatter.initialize()
        output = formatter.format({"panes": {"test": {}}})
        # Compact has no newlines in body
        lines = output.strip().split("\n")
        assert len(lines) == 1


class TestPrometheusFormatterOutput:
    """Tests for Prometheus formatter output."""

    def test_format_empty_panes(self) -> None:
        """Test formatting with no panes."""
        formatter = PrometheusFormatter()
        formatter.initialize()
        output = formatter.format({"panes": {}})
        # Should be empty or just newline
        assert output.strip() == ""

    def test_format_with_numeric_data(self) -> None:
        """Test formatting with numeric data."""

        class TestData(MetricData):
            value: int = 42

        formatter = PrometheusFormatter()
        formatter.initialize()
        output = formatter.format({"panes": {"test": TestData()}})
        assert "uptop_test_value" in output
        assert "42" in output

    def test_metric_name_sanitization(self) -> None:
        """Test metric names are sanitized."""

        class TestData(MetricData):
            my_value: int = 42

        formatter = PrometheusFormatter()
        formatter.initialize()
        output = formatter.format({"panes": {"test-pane": TestData()}})
        # Hyphens should be converted to underscores
        assert "test_pane" in output or "test-pane" not in output.split("\n")[0]
