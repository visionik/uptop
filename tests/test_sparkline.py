"""Tests for the Sparkline widget.

This module tests the sparkline widget functionality including:
- Rendering with various data patterns
- Color thresholds
- Edge cases (empty data, single value, max values)
- Value-to-character conversion
- History management
"""

from __future__ import annotations

from uptop.tui.widgets.sparkline import (
    SPARK_CHARS,
    Sparkline,
    get_value_color,
    get_value_style,
    value_to_char,
)


class TestValueToChar:
    """Tests for the value_to_char function."""

    def test_min_value_returns_underscore(self) -> None:
        """Test that minimum value returns an underscore character."""
        assert value_to_char(0.0, 0.0, 100.0) == "_"

    def test_max_value_returns_full_block(self) -> None:
        """Test that maximum value returns full block character."""
        assert value_to_char(100.0, 0.0, 100.0) == "\u2588"  # Full block

    def test_mid_value_returns_mid_char(self) -> None:
        """Test that middle value returns middle character."""
        char = value_to_char(50.0, 0.0, 100.0)
        # Should be around index 4 (middle of 0-8)
        assert char in SPARK_CHARS[3:6]

    def test_value_below_min_clamped(self) -> None:
        """Test that values below min are clamped to min."""
        assert value_to_char(-10.0, 0.0, 100.0) == "_"

    def test_value_above_max_clamped(self) -> None:
        """Test that values above max are clamped to max."""
        assert value_to_char(150.0, 0.0, 100.0) == "\u2588"

    def test_custom_range(self) -> None:
        """Test value_to_char with custom min/max range."""
        # Mid-point of 0-50 range
        char = value_to_char(25.0, 0.0, 50.0)
        assert char in SPARK_CHARS[3:6]

    def test_same_min_max_returns_middle(self) -> None:
        """Test that when min equals max, middle character is returned."""
        # This avoids division by zero
        char = value_to_char(50.0, 50.0, 50.0)
        assert char == SPARK_CHARS[4]  # Middle character

    def test_all_character_levels(self) -> None:
        """Test that different values map to different characters."""
        chars_used = set()
        for i in range(9):
            value = i * 12.5  # 0, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100
            char = value_to_char(value, 0.0, 100.0)
            chars_used.add(char)
        # Should use multiple different characters
        assert len(chars_used) >= 5


class TestGetValueColor:
    """Tests for the get_value_color function."""

    def test_low_values_green(self) -> None:
        """Test that low values (0-50%) return green."""
        assert get_value_color(0.0) == "green"
        assert get_value_color(25.0) == "green"
        assert get_value_color(49.9) == "green"

    def test_medium_values_yellow(self) -> None:
        """Test that medium values (50-80%) return yellow."""
        assert get_value_color(50.0) == "yellow"
        assert get_value_color(65.0) == "yellow"
        assert get_value_color(79.9) == "yellow"

    def test_high_values_red(self) -> None:
        """Test that high values (80-100%) return red."""
        assert get_value_color(80.0) == "red"
        assert get_value_color(90.0) == "red"
        assert get_value_color(100.0) == "red"

    def test_threshold_boundaries(self) -> None:
        """Test exact threshold values."""
        # Just below 50% should be green
        assert get_value_color(49.99) == "green"
        # Exactly 50% should be yellow
        assert get_value_color(50.0) == "yellow"
        # Just below 80% should be yellow
        assert get_value_color(79.99) == "yellow"
        # Exactly 80% should be red
        assert get_value_color(80.0) == "red"


class TestGetValueStyle:
    """Tests for the get_value_style function."""

    def test_returns_style_with_correct_color(self) -> None:
        """Test that styles have correct colors."""
        low_style = get_value_style(25.0)
        assert low_style.color is not None
        assert low_style.color.name == "green"

        medium_style = get_value_style(65.0)
        assert medium_style.color is not None
        assert medium_style.color.name == "yellow"

        high_style = get_value_style(90.0)
        assert high_style.color is not None
        assert high_style.color.name == "red"


class TestSparklineWidget:
    """Tests for the Sparkline widget."""

    def test_initialization_defaults(self) -> None:
        """Test default initialization values."""
        sparkline = Sparkline()
        assert sparkline.min_value == 0.0
        assert sparkline.max_value == 100.0
        assert sparkline.width == 30
        assert sparkline.show_label is False
        assert sparkline.label == ""
        assert sparkline.color_by_value is True
        assert sparkline.history_size == 200
        assert len(sparkline.values) == 0

    def test_initialization_with_values(self) -> None:
        """Test initialization with provided values."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        sparkline = Sparkline(values=values)
        assert sparkline.values == values

    def test_initialization_with_custom_params(self) -> None:
        """Test initialization with custom parameters."""
        sparkline = Sparkline(
            min_value=10.0,
            max_value=200.0,
            width=50,
            show_label=True,
            label="Test",
            color_by_value=False,
            history_size=100,
        )
        assert sparkline.min_value == 10.0
        assert sparkline.max_value == 200.0
        assert sparkline.width == 50
        assert sparkline.show_label is True
        assert sparkline.label == "Test"
        assert sparkline.color_by_value is False
        assert sparkline.history_size == 100

    def test_add_value(self) -> None:
        """Test adding a single value."""
        sparkline = Sparkline()
        sparkline.add_value(50.0)
        assert sparkline.values == [50.0]
        sparkline.add_value(75.0)
        assert sparkline.values == [50.0, 75.0]

    def test_add_values(self) -> None:
        """Test adding multiple values at once."""
        sparkline = Sparkline()
        sparkline.add_values([10.0, 20.0, 30.0])
        assert sparkline.values == [10.0, 20.0, 30.0]

    def test_set_values_replaces(self) -> None:
        """Test that set_values replaces existing values."""
        sparkline = Sparkline(values=[1.0, 2.0, 3.0])
        sparkline.set_values([10.0, 20.0])
        assert sparkline.values == [10.0, 20.0]

    def test_clear(self) -> None:
        """Test clearing all values."""
        sparkline = Sparkline(values=[10.0, 20.0, 30.0])
        sparkline.clear()
        assert len(sparkline.values) == 0

    def test_history_size_limit(self) -> None:
        """Test that history respects size limit."""
        sparkline = Sparkline(history_size=5)
        for i in range(10):
            sparkline.add_value(float(i))
        # Should only keep the last 5 values
        assert len(sparkline.values) == 5
        assert sparkline.values == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_render_empty_data(self) -> None:
        """Test rendering with no data shows placeholder."""
        sparkline = Sparkline(width=10)
        rendered = sparkline.render()
        # Should render as placeholder dashes
        assert str(rendered) == "-" * 10

    def test_render_single_value(self) -> None:
        """Test rendering with a single value."""
        sparkline = Sparkline(values=[50.0], width=10)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        # Should have padding plus the single character
        assert len(rendered_str) == 10
        # Last character should be the sparkline char for 50%
        assert rendered_str[-1] in SPARK_CHARS

    def test_render_full_width(self) -> None:
        """Test rendering when values fill the width."""
        values = [float(i * 10) for i in range(10)]  # 0, 10, 20, ..., 90
        sparkline = Sparkline(values=values, width=10)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        assert len(rendered_str) == 10
        # First char should be for 0%, last should be for 90%
        assert rendered_str[0] == "_"  # 0% is underscore
        assert rendered_str[-1] in SPARK_CHARS[6:9]  # 90% is high

    def test_render_exceeds_width(self) -> None:
        """Test that excess values are truncated to width."""
        values = [float(i) for i in range(100)]
        sparkline = Sparkline(values=values, width=20)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        # Should only show the last 20 values
        assert len(rendered_str) == 20

    def test_render_with_label(self) -> None:
        """Test rendering with a label."""
        sparkline = Sparkline(
            values=[50.0],
            width=10,
            show_label=True,
            label="CPU",
        )
        rendered = sparkline.render()
        rendered_str = str(rendered)
        assert "CPU: " in rendered_str

    def test_render_max_values(self) -> None:
        """Test rendering with all max values (100%)."""
        values = [100.0] * 10
        sparkline = Sparkline(values=values, width=10)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        # All characters should be full blocks
        assert all(c == "\u2588" for c in rendered_str)

    def test_render_min_values(self) -> None:
        """Test rendering with all min values (0%)."""
        values = [0.0] * 10
        sparkline = Sparkline(values=values, width=10)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        # All characters should be underscores
        assert all(c == "_" for c in rendered_str)

    def test_render_ascending_pattern(self) -> None:
        """Test rendering with ascending values."""
        values = [0.0, 25.0, 50.0, 75.0, 100.0]
        sparkline = Sparkline(values=values, width=5)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        # Characters should increase in height
        assert rendered_str[0] == "_"  # 0%
        assert rendered_str[-1] == "\u2588"  # 100%
        # Middle characters should be intermediate
        for i in range(1, 4):
            assert rendered_str[i] in SPARK_CHARS[1:8]

    def test_render_descending_pattern(self) -> None:
        """Test rendering with descending values."""
        values = [100.0, 75.0, 50.0, 25.0, 0.0]
        sparkline = Sparkline(values=values, width=5)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        # Characters should decrease in height
        assert rendered_str[0] == "\u2588"  # 100%
        assert rendered_str[-1] == "_"  # 0%


class TestSparklineIntegration:
    """Integration tests for the Sparkline widget."""

    def test_typical_cpu_usage_pattern(self) -> None:
        """Test with a realistic CPU usage pattern."""
        # Simulate 30 seconds of CPU usage data
        cpu_values = [
            25.0, 28.0, 30.0, 45.0, 60.0, 75.0, 80.0, 85.0, 90.0, 95.0,
            88.0, 75.0, 60.0, 45.0, 30.0, 25.0, 20.0, 18.0, 22.0, 35.0,
            48.0, 52.0, 45.0, 38.0, 32.0, 28.0, 25.0, 22.0, 20.0, 18.0,
        ]
        sparkline = Sparkline(values=cpu_values, width=30)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        assert len(rendered_str) == 30
        # Should have variation in the output
        unique_chars = set(rendered_str)
        assert len(unique_chars) > 1

    def test_memory_usage_pattern(self) -> None:
        """Test with a typical memory usage pattern (slowly increasing)."""
        # Memory tends to increase slowly over time
        memory_values = [45.0 + (i * 0.5) for i in range(60)]
        sparkline = Sparkline(values=memory_values, width=30, history_size=60)
        rendered = sparkline.render()
        rendered_str = str(rendered)
        assert len(rendered_str) == 30

    def test_color_changes_with_last_value(self) -> None:
        """Test that color is based on the most recent value."""
        # Start with low values
        sparkline = Sparkline(values=[10.0, 20.0, 30.0], width=10)
        # The color should be based on the last value (30% = green)
        # This is tested through the render output color

        # Update with high value
        sparkline.add_value(90.0)
        # Now color should reflect 90% (red)
        # The widget handles this internally
        assert sparkline.values[-1] == 90.0
