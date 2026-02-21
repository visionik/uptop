"""Tests for the OpenTelemetry widget."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from uptop.models.base import DisplayMode
from uptop.plugins.otel import OTelData
from uptop.tui.panes.otel_widget import (
    OTelWidget,
    format_cost,
    format_duration,
    format_event_type,
    format_tokens,
    get_cost_color,
)


class TestFormatTokens:
    """Tests for the format_tokens helper."""

    def test_small_numbers(self) -> None:
        assert format_tokens(0) == "0"
        assert format_tokens(999) == "999"

    def test_thousands(self) -> None:
        assert format_tokens(1000) == "1.0k"
        assert format_tokens(12345) == "12.3k"
        assert format_tokens(999999) == "1000.0k"

    def test_millions(self) -> None:
        assert format_tokens(1_000_000) == "1.0M"
        assert format_tokens(2_500_000) == "2.5M"


class TestFormatCost:
    """Tests for the format_cost helper."""

    def test_small_cost(self) -> None:
        assert format_cost(0.0) == "$0.00"
        assert format_cost(0.42) == "$0.42"
        assert format_cost(9.99) == "$9.99"

    def test_medium_cost(self) -> None:
        assert format_cost(10.0) == "$10.0"
        assert format_cost(42.5) == "$42.5"

    def test_large_cost(self) -> None:
        assert format_cost(100.0) == "$100"
        assert format_cost(1234.56) == "$1235"


class TestGetCostColor:
    """Tests for cost color thresholds."""

    def test_green_under_one(self) -> None:
        assert get_cost_color(0.0) == "green"
        assert get_cost_color(0.99) == "green"

    def test_yellow_one_to_five(self) -> None:
        assert get_cost_color(1.0) == "yellow"
        assert get_cost_color(4.99) == "yellow"

    def test_red_five_and_above(self) -> None:
        assert get_cost_color(5.0) == "red"
        assert get_cost_color(100.0) == "red"


class TestFormatDuration:
    """Tests for format_duration helper."""

    def test_seconds(self) -> None:
        assert format_duration(0) == "0s"
        assert format_duration(30) == "30s"
        assert format_duration(59) == "59s"

    def test_minutes(self) -> None:
        assert format_duration(60) == "1.0m"
        assert format_duration(150) == "2.5m"

    def test_hours(self) -> None:
        assert format_duration(3600) == "1.0h"
        assert format_duration(5400) == "1.5h"


class TestFormatEventType:
    """Tests for event type formatting."""

    def test_known_types(self) -> None:
        assert format_event_type("tool_result") == "[T]"
        assert format_event_type("api_request") == "[A]"
        assert format_event_type("user_prompt") == "[U]"
        assert format_event_type("session_start") == "[S]"

    def test_unknown_type(self) -> None:
        assert format_event_type("unknown_event") == "[*]"


class TestOTelWidget:
    """Tests for the OTelWidget."""

    def test_instantiation_without_data(self) -> None:
        widget = OTelWidget()
        assert widget.data is None

    def test_instantiation_with_data(self) -> None:
        data = OTelData(total_tokens=5000, total_cost_usd=0.42)
        widget = OTelWidget(data=data)
        assert widget.data is not None
        assert widget.data.total_tokens == 5000

    def test_default_display_mode(self) -> None:
        widget = OTelWidget()
        assert widget._display_mode == DisplayMode.MINIMIZED

    def test_render_micro_with_data(self) -> None:
        data = OTelData(
            total_cost_usd=0.42,
            total_tokens=12345,
            session_count=2,
        )
        widget = OTelWidget(data=data)
        result = widget._render_micro()
        assert "OTel:" in result
        assert "12.3k" in result
        assert "2 sessions" in result

    def test_render_micro_no_data(self) -> None:
        widget = OTelWidget()
        result = widget._render_micro()
        assert "OTel: --" in result

    def test_render_minimized_with_data(self) -> None:
        data = OTelData(
            total_cost_usd=2.50,
            total_tokens=10000,
            input_tokens=6000,
            output_tokens=4000,
            session_count=3,
            event_count=42,
            receiver_running=True,
        )
        widget = OTelWidget(data=data)
        result = widget._render_minimized()
        assert "Cost:" in result
        assert "Tokens:" in result
        assert "Sessions:" in result
        assert "Events:" in result
        assert "Receiving" in result

    def test_render_minimized_no_data(self) -> None:
        widget = OTelWidget()
        result = widget._render_minimized()
        assert "Waiting" in result

    def test_render_medium_with_data(self) -> None:
        data = OTelData(
            total_cost_usd=1.23,
            total_tokens=50000,
            input_tokens=30000,
            output_tokens=20000,
            cache_read_tokens=5000,
            cache_creation_tokens=1000,
            session_count=1,
            active_duration_seconds=300,
            lines_of_code=150,
            num_commits=3,
            num_prs=1,
            event_count=10,
            recent_events=[
                {
                    "timestamp": "2024-01-01T12:00:00+00:00",
                    "name": "tool_result",
                    "severity": "INFO",
                    "attributes": {"tool": "bash"},
                }
            ],
            receiver_running=True,
        )
        widget = OTelWidget(data=data)
        result = widget._render_medium()
        assert "Metrics" in result
        assert "Recent Events" in result
        assert "tool_result" in result
        assert "Cache" in result
        assert "Duration" in result
        assert "Code" in result

    def test_render_medium_no_events(self) -> None:
        data = OTelData(receiver_running=False)
        widget = OTelWidget(data=data)
        result = widget._render_medium()
        assert "No events yet" in result

    def test_render_maximized_with_data(self) -> None:
        data = OTelData(
            total_cost_usd=5.67,
            total_tokens=100000,
            input_tokens=60000,
            output_tokens=40000,
            cache_read_tokens=10000,
            cache_creation_tokens=2000,
            session_count=5,
            active_duration_seconds=7200,
            lines_of_code=500,
            num_commits=10,
            num_prs=2,
            event_count=100,
            recent_events=[
                {
                    "timestamp": "2024-01-01T12:00:00+00:00",
                    "name": "api_request",
                    "severity": "INFO",
                    "attributes": {"model": "claude-3"},
                },
                {
                    "timestamp": "2024-01-01T12:00:01+00:00",
                    "name": "tool_result",
                    "severity": "WARN",
                    "attributes": {},
                },
            ],
            receiver_running=True,
            last_updated=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        widget = OTelWidget(data=data)
        result = widget._render_maximized()
        assert "Token Usage" in result
        assert "Cost & Activity" in result
        assert "Event Log" in result
        assert "100,000" in result  # Full token count
        assert "Pull Requests" in result
        assert "api_request" in result
        assert "tool_result" in result

    def test_render_maximized_no_data(self) -> None:
        widget = OTelWidget()
        result = widget._render_maximized()
        assert "Waiting" in result

    def test_cost_color_in_micro(self) -> None:
        """Test that cost color is applied in micro mode."""
        # Green cost
        data = OTelData(total_cost_usd=0.5)
        widget = OTelWidget(data=data)
        result = widget._render_micro()
        assert "green" in result

        # Red cost
        data = OTelData(total_cost_usd=10.0)
        widget = OTelWidget(data=data)
        result = widget._render_micro()
        assert "red" in result

    def test_update_data(self) -> None:
        widget = OTelWidget()
        data = OTelData(total_tokens=5000)
        widget.update_data(data)
        assert widget.data is not None
        assert widget.data.total_tokens == 5000

    def test_update_data_with_mode(self) -> None:
        widget = OTelWidget()
        data = OTelData(total_tokens=5000)
        widget.update_data(data, mode=DisplayMode.MAXIMIZED)
        assert widget._display_mode == DisplayMode.MAXIMIZED
        assert widget.data is not None
