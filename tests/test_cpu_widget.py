"""Tests for the CPU widget."""

import pytest
from rich.text import Text

from uptop.plugins.cpu import CPUCore, CPUData
from uptop.tui.panes.cpu_widget import (
    THRESHOLD_LOW,
    THRESHOLD_MEDIUM,
    CoreUsageRow,
    CPUProgressBar,
    CPUWidget,
    get_usage_color,
    get_usage_style,
)


class TestGetUsageColor:
    """Tests for the get_usage_color function."""

    def test_low_usage_returns_green(self) -> None:
        """Test that usage below 50% returns green."""
        assert get_usage_color(0.0) == "green"
        assert get_usage_color(25.0) == "green"
        assert get_usage_color(49.9) == "green"

    def test_medium_usage_returns_yellow(self) -> None:
        """Test that usage between 50-80% returns yellow."""
        assert get_usage_color(50.0) == "yellow"
        assert get_usage_color(65.0) == "yellow"
        assert get_usage_color(79.9) == "yellow"

    def test_high_usage_returns_red(self) -> None:
        """Test that usage above 80% returns red."""
        assert get_usage_color(80.0) == "red"
        assert get_usage_color(90.0) == "red"
        assert get_usage_color(100.0) == "red"

    def test_threshold_boundaries(self) -> None:
        """Test exact threshold boundaries."""
        # Just below THRESHOLD_LOW should be green
        assert get_usage_color(THRESHOLD_LOW - 0.1) == "green"
        # At THRESHOLD_LOW should be yellow
        assert get_usage_color(THRESHOLD_LOW) == "yellow"
        # Just below THRESHOLD_MEDIUM should be yellow
        assert get_usage_color(THRESHOLD_MEDIUM - 0.1) == "yellow"
        # At THRESHOLD_MEDIUM should be red
        assert get_usage_color(THRESHOLD_MEDIUM) == "red"


class TestGetUsageStyle:
    """Tests for the get_usage_style function."""

    def test_returns_style_with_correct_color(self) -> None:
        """Test that style has correct color attribute."""
        style_low = get_usage_style(25.0)
        assert style_low.color is not None
        assert style_low.color.name == "green"

        style_medium = get_usage_style(65.0)
        assert style_medium.color is not None
        assert style_medium.color.name == "yellow"

        style_high = get_usage_style(90.0)
        assert style_high.color is not None
        assert style_high.color.name == "red"


class TestCPUProgressBar:
    """Tests for the CPUProgressBar widget."""

    def test_instantiation(self) -> None:
        """Test basic widget instantiation."""
        bar = CPUProgressBar()
        assert bar.usage_percent == 0.0
        assert bar.bar_width == 20

    def test_instantiation_with_values(self) -> None:
        """Test instantiation with custom values."""
        bar = CPUProgressBar(usage_percent=75.5, bar_width=30)
        assert bar.usage_percent == 75.5
        assert bar.bar_width == 30

    def test_render_returns_text(self) -> None:
        """Test that render returns a Rich Text object."""
        bar = CPUProgressBar(usage_percent=50.0)
        result = bar.render()
        assert isinstance(result, Text)

    def test_render_contains_brackets(self) -> None:
        """Test that render output contains progress bar brackets."""
        bar = CPUProgressBar(usage_percent=50.0)
        result = bar.render()
        plain_text = result.plain
        assert "[" in plain_text
        assert "]" in plain_text

    def test_render_zero_percent(self) -> None:
        """Test rendering at 0% shows empty bar."""
        bar = CPUProgressBar(usage_percent=0.0, bar_width=10)
        result = bar.render()
        plain_text = result.plain
        # Should have no filled characters (all spaces inside brackets)
        assert plain_text == "[" + " " * 10 + "]"

    def test_render_full_percent(self) -> None:
        """Test rendering at 100% shows full bar."""
        bar = CPUProgressBar(usage_percent=100.0, bar_width=10)
        result = bar.render()
        plain_text = result.plain
        # Should have all filled characters
        assert plain_text == "[" + "=" * 10 + "]"


class TestCoreUsageRow:
    """Tests for the CoreUsageRow widget."""

    def test_instantiation(self) -> None:
        """Test basic widget instantiation."""
        row = CoreUsageRow(core_id=0, usage_percent=50.0)
        assert row.core_id == 0
        assert row.usage_percent == 50.0

    def test_instantiation_various_cores(self) -> None:
        """Test instantiation with various core IDs."""
        row = CoreUsageRow(core_id=15, usage_percent=75.0)
        assert row.core_id == 15
        assert row.usage_percent == 75.0


class TestCPUWidget:
    """Tests for the main CPUWidget."""

    def test_instantiation_without_data(self) -> None:
        """Test widget can be instantiated without data."""
        widget = CPUWidget()
        assert widget.cpu_data is None

    def test_instantiation_with_data(self) -> None:
        """Test widget can be instantiated with data."""
        cores = [CPUCore(id=0, usage_percent=50.0)]
        data = CPUData(cores=cores)
        widget = CPUWidget(cpu_data=data)
        assert widget.cpu_data is data

    def test_update_data_method(self) -> None:
        """Test the update_data convenience method."""
        widget = CPUWidget()
        cores = [CPUCore(id=0, usage_percent=75.0)]
        data = CPUData(cores=cores)
        widget.update_data(data)
        assert widget.cpu_data is data

    def test_get_usage_color_class_low(self) -> None:
        """Test _get_usage_color_class for low usage."""
        widget = CPUWidget()
        assert widget._get_usage_color_class(25.0) == ""
        assert widget._get_usage_color_class(49.9) == ""

    def test_get_usage_color_class_medium(self) -> None:
        """Test _get_usage_color_class for medium usage."""
        widget = CPUWidget()
        assert widget._get_usage_color_class(50.0) == "medium"
        assert widget._get_usage_color_class(79.9) == "medium"

    def test_get_usage_color_class_high(self) -> None:
        """Test _get_usage_color_class for high usage."""
        widget = CPUWidget()
        assert widget._get_usage_color_class(80.0) == "high"
        assert widget._get_usage_color_class(100.0) == "high"

    def test_render_load_averages_no_data(self) -> None:
        """Test _render_load_averages with no data."""
        widget = CPUWidget()
        result = widget._render_load_averages()
        assert isinstance(result, Text)
        assert "No data" in result.plain

    def test_render_load_averages_with_data(self) -> None:
        """Test _render_load_averages with valid data."""
        data = CPUData(
            load_avg_1min=1.50,
            load_avg_5min=2.25,
            load_avg_15min=1.75,
        )
        widget = CPUWidget(cpu_data=data)
        result = widget._render_load_averages()
        assert isinstance(result, Text)
        assert "Load Avg:" in result.plain
        assert "1.50" in result.plain
        assert "2.25" in result.plain
        assert "1.75" in result.plain

    def test_render_frequency_info_no_data(self) -> None:
        """Test _render_frequency_info with no data."""
        widget = CPUWidget()
        result = widget._render_frequency_info()
        assert result is None

    def test_render_frequency_info_no_freq(self) -> None:
        """Test _render_frequency_info when cores have no frequency."""
        cores = [CPUCore(id=0, usage_percent=50.0)]  # No freq_mhz
        data = CPUData(cores=cores)
        widget = CPUWidget(cpu_data=data)
        result = widget._render_frequency_info()
        assert result is None

    def test_render_frequency_info_with_freq(self) -> None:
        """Test _render_frequency_info when cores have frequency."""
        cores = [
            CPUCore(id=0, usage_percent=50.0, freq_mhz=3000.0),
            CPUCore(id=1, usage_percent=50.0, freq_mhz=3200.0),
        ]
        data = CPUData(cores=cores)
        widget = CPUWidget(cpu_data=data)
        result = widget._render_frequency_info()
        assert result is not None
        assert isinstance(result, Text)
        assert "Frequency:" in result.plain
        assert "MHz" in result.plain


class TestCPUWidgetColorThresholds:
    """Tests specifically for color threshold behavior."""

    def test_total_usage_green_color_class(self) -> None:
        """Test that low total usage results in no color class (default green)."""
        cores = [CPUCore(id=0, usage_percent=25.0)]
        data = CPUData(cores=cores)
        widget = CPUWidget(cpu_data=data)
        color_class = widget._get_usage_color_class(data.total_usage_percent)
        assert color_class == "", "Expected no class (default green) for low usage"

    def test_total_usage_yellow_color_class(self) -> None:
        """Test that medium total usage results in 'medium' color class."""
        cores = [CPUCore(id=0, usage_percent=65.0)]
        data = CPUData(cores=cores)
        widget = CPUWidget(cpu_data=data)
        color_class = widget._get_usage_color_class(data.total_usage_percent)
        assert color_class == "medium", "Expected 'medium' class for medium usage"

    def test_total_usage_red_color_class(self) -> None:
        """Test that high total usage results in 'high' color class."""
        cores = [CPUCore(id=0, usage_percent=95.0)]
        data = CPUData(cores=cores)
        widget = CPUWidget(cpu_data=data)
        color_class = widget._get_usage_color_class(data.total_usage_percent)
        assert color_class == "high", "Expected 'high' class for high usage"


class TestCPUWidgetWithSampleData:
    """Integration tests with realistic sample data."""

    @pytest.fixture
    def sample_cpu_data(self) -> CPUData:
        """Create sample CPU data for testing."""
        cores = [
            CPUCore(id=0, usage_percent=25.0, freq_mhz=3600.0, temp_celsius=55.0),
            CPUCore(id=1, usage_percent=50.0, freq_mhz=3400.0, temp_celsius=58.0),
            CPUCore(id=2, usage_percent=75.0, freq_mhz=3500.0, temp_celsius=62.0),
            CPUCore(id=3, usage_percent=90.0, freq_mhz=3300.0, temp_celsius=68.0),
        ]
        return CPUData(
            cores=cores,
            load_avg_1min=2.5,
            load_avg_5min=2.0,
            load_avg_15min=1.5,
        )

    def test_widget_with_sample_data(self, sample_cpu_data: CPUData) -> None:
        """Test widget renders correctly with sample data."""
        widget = CPUWidget(cpu_data=sample_cpu_data)

        # Check total usage (average of 25, 50, 75, 90 = 60%)
        assert sample_cpu_data.total_usage_percent == 60.0
        assert sample_cpu_data.core_count == 4

        # Check color class for 60% usage (medium)
        color_class = widget._get_usage_color_class(sample_cpu_data.total_usage_percent)
        assert color_class == "medium"

        # Check load averages
        load_result = widget._render_load_averages()
        assert "2.50" in load_result.plain
        assert "2.00" in load_result.plain
        assert "1.50" in load_result.plain

        # Check frequency info
        freq_result = widget._render_frequency_info()
        assert freq_result is not None
        assert "MHz" in freq_result.plain

    def test_core_usage_rows_instantiate(self, sample_cpu_data: CPUData) -> None:
        """Test that core usage rows can be instantiated correctly."""
        for core in sample_cpu_data.cores:
            row = CoreUsageRow(
                core_id=core.id,
                usage_percent=core.usage_percent,
            )
            assert row.core_id == core.id
            assert row.usage_percent == core.usage_percent
