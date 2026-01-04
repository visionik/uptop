"""Tests for the Memory Widget.

This module tests the MemoryWidget functionality including:
- Widget instantiation
- Rendering with sample MemoryData
- Size formatting utilities
- Color coding based on usage
- RAM and Swap display
"""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label, ProgressBar

from uptop.plugins.memory import MemoryData, SwapMemory, VirtualMemory
from uptop.tui.panes.memory_widget import (
    MemoryBar,
    MemoryDetails,
    MemoryWidget,
    format_bytes,
    get_usage_color,
)

# ============================================================================
# Test Fixtures
# ============================================================================


def create_sample_memory_data(
    ram_total: int = 16_000_000_000,
    ram_used: int = 8_000_000_000,
    ram_available: int = 8_000_000_000,
    ram_percent: float = 50.0,
    ram_cached: int | None = 2_000_000_000,
    ram_buffers: int | None = 500_000_000,
    swap_total: int = 8_000_000_000,
    swap_used: int = 2_000_000_000,
    swap_free: int = 6_000_000_000,
    swap_percent: float = 25.0,
) -> MemoryData:
    """Create sample MemoryData for testing.

    Args:
        ram_total: Total RAM in bytes
        ram_used: Used RAM in bytes
        ram_available: Available RAM in bytes
        ram_percent: RAM usage percentage
        ram_cached: Cached RAM in bytes (optional)
        ram_buffers: Buffer RAM in bytes (optional)
        swap_total: Total swap in bytes
        swap_used: Used swap in bytes
        swap_free: Free swap in bytes
        swap_percent: Swap usage percentage

    Returns:
        MemoryData instance with specified values
    """
    virtual = VirtualMemory(
        total_bytes=ram_total,
        used_bytes=ram_used,
        available_bytes=ram_available,
        percent=ram_percent,
        cached_bytes=ram_cached,
        buffers_bytes=ram_buffers,
    )
    swap = SwapMemory(
        total_bytes=swap_total,
        used_bytes=swap_used,
        free_bytes=swap_free,
        percent=swap_percent,
    )
    return MemoryData(virtual=virtual, swap=swap, source="memory")


# ============================================================================
# format_bytes Tests
# ============================================================================


class TestFormatBytes:
    """Tests for format_bytes utility function."""

    def test_format_bytes_zero(self) -> None:
        """Test formatting zero bytes."""
        assert format_bytes(0) == "0 B"

    def test_format_bytes_small(self) -> None:
        """Test formatting small byte values."""
        assert format_bytes(100) == "100 B"
        assert format_bytes(1023) == "1023 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobyte values."""
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(10240) == "10.0 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabyte values."""
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(512 * 1024 * 1024) == "512.0 MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabyte values."""
        assert format_bytes(1024**3) == "1.0 GB"
        assert format_bytes(16 * 1024**3) == "16.0 GB"

    def test_format_bytes_terabytes(self) -> None:
        """Test formatting terabyte values."""
        assert format_bytes(1024**4) == "1.0 TB"
        assert format_bytes(2 * 1024**4) == "2.0 TB"

    def test_format_bytes_petabytes(self) -> None:
        """Test formatting petabyte values."""
        assert format_bytes(1024**5) == "1.0 PB"

    def test_format_bytes_negative(self) -> None:
        """Test that negative values return '0 B'."""
        assert format_bytes(-100) == "0 B"
        assert format_bytes(-1024) == "0 B"


# ============================================================================
# get_usage_color Tests
# ============================================================================


class TestGetUsageColor:
    """Tests for get_usage_color utility function."""

    def test_low_usage(self) -> None:
        """Test color for low usage (0-60%)."""
        assert get_usage_color(0) == "low"
        assert get_usage_color(30) == "low"
        assert get_usage_color(59.9) == "low"

    def test_medium_usage(self) -> None:
        """Test color for medium usage (60-85%)."""
        assert get_usage_color(60) == "medium"
        assert get_usage_color(70) == "medium"
        assert get_usage_color(84.9) == "medium"

    def test_high_usage(self) -> None:
        """Test color for high usage (85-100%)."""
        assert get_usage_color(85) == "high"
        assert get_usage_color(90) == "high"
        assert get_usage_color(100) == "high"

    def test_boundary_values(self) -> None:
        """Test exact boundary values."""
        assert get_usage_color(59.99) == "low"
        assert get_usage_color(60.0) == "medium"
        assert get_usage_color(84.99) == "medium"
        assert get_usage_color(85.0) == "high"


# ============================================================================
# MemoryBar Widget Tests
# ============================================================================


class MemoryBarTestApp(App[None]):
    """Test app for MemoryBar widget testing."""

    def __init__(
        self,
        label: str = "RAM",
        percent: float = 50.0,
    ) -> None:
        """Initialize test app with configurable memory bar.

        Args:
            label: Bar label
            percent: Usage percentage
        """
        super().__init__()
        self._label = label
        self._percent = percent

    def compose(self) -> ComposeResult:
        """Compose the test app with a MemoryBar."""
        yield MemoryBar(label=self._label, percent=self._percent, id="test-bar")


class TestMemoryBar:
    """Tests for MemoryBar widget."""

    def test_memory_bar_initialization(self) -> None:
        """Test MemoryBar initializes with correct defaults."""
        bar = MemoryBar()
        assert bar.label == "MEM"
        assert bar.percent == 0.0

    def test_memory_bar_custom_values(self) -> None:
        """Test MemoryBar initializes with custom values."""
        bar = MemoryBar(label="RAM", percent=75.5)
        assert bar.label == "RAM"
        assert bar.percent == 75.5

    @pytest.mark.asyncio
    async def test_memory_bar_renders(self) -> None:
        """Test that MemoryBar renders correctly."""
        app = MemoryBarTestApp(label="RAM", percent=50.0)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#test-bar", MemoryBar)
            assert bar is not None
            assert bar.label == "RAM"
            assert bar.percent == 50.0

    @pytest.mark.asyncio
    async def test_memory_bar_has_progress_bar(self) -> None:
        """Test that MemoryBar contains a progress bar."""
        app = MemoryBarTestApp(percent=50.0)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#test-bar", MemoryBar)
            progress = bar.query_one("#progress", ProgressBar)
            assert progress is not None

    @pytest.mark.asyncio
    async def test_memory_bar_has_labels(self) -> None:
        """Test that MemoryBar has label and percent labels."""
        app = MemoryBarTestApp(label="Swap", percent=25.0)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#test-bar", MemoryBar)
            label = bar.query_one(".bar-label", Label)
            assert label is not None

    @pytest.mark.asyncio
    async def test_memory_bar_color_class_low(self) -> None:
        """Test that low usage gets 'low' class."""
        app = MemoryBarTestApp(percent=30.0)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#test-bar", MemoryBar)
            assert "low" in bar.classes

    @pytest.mark.asyncio
    async def test_memory_bar_color_class_medium(self) -> None:
        """Test that medium usage gets 'medium' class."""
        app = MemoryBarTestApp(percent=70.0)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#test-bar", MemoryBar)
            assert "medium" in bar.classes

    @pytest.mark.asyncio
    async def test_memory_bar_color_class_high(self) -> None:
        """Test that high usage gets 'high' class."""
        app = MemoryBarTestApp(percent=90.0)
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one("#test-bar", MemoryBar)
            assert "high" in bar.classes


# ============================================================================
# MemoryDetails Widget Tests
# ============================================================================


class MemoryDetailsTestApp(App[None]):
    """Test app for MemoryDetails widget testing."""

    def __init__(self, details: list[tuple[str, str]]) -> None:
        """Initialize test app with configurable details.

        Args:
            details: List of (label, value) tuples
        """
        super().__init__()
        self._details = details

    def compose(self) -> ComposeResult:
        """Compose the test app with a MemoryDetails."""
        yield MemoryDetails(details=self._details, id="test-details")


class TestMemoryDetails:
    """Tests for MemoryDetails widget."""

    def test_memory_details_initialization(self) -> None:
        """Test MemoryDetails initializes correctly."""
        details = [("Total", "16.0 GB"), ("Used", "8.0 GB")]
        widget = MemoryDetails(details=details)
        assert widget._details == details

    @pytest.mark.asyncio
    async def test_memory_details_renders(self) -> None:
        """Test that MemoryDetails renders correctly."""
        details = [("Total", "16.0 GB"), ("Used", "8.0 GB")]
        app = MemoryDetailsTestApp(details=details)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-details", MemoryDetails)
            assert widget is not None


# ============================================================================
# MemoryWidget Tests
# ============================================================================


class MemoryWidgetTestApp(App[None]):
    """Test app for MemoryWidget widget testing."""

    def __init__(self, data: MemoryData | None = None) -> None:
        """Initialize test app with configurable memory widget.

        Args:
            data: Optional MemoryData to display
        """
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        """Compose the test app with a MemoryWidget."""
        yield MemoryWidget(data=self._data, id="test-widget")


class TestMemoryWidget:
    """Tests for MemoryWidget widget."""

    def test_memory_widget_initialization_no_data(self) -> None:
        """Test MemoryWidget initializes correctly without data."""
        widget = MemoryWidget()
        assert widget.data is None

    def test_memory_widget_initialization_with_data(self) -> None:
        """Test MemoryWidget initializes correctly with data."""
        data = create_sample_memory_data()
        widget = MemoryWidget(data=data)
        assert widget.data is not None
        assert widget.data.virtual.percent == 50.0

    @pytest.mark.asyncio
    async def test_memory_widget_renders_no_data(self) -> None:
        """Test that MemoryWidget renders correctly without data."""
        app = MemoryWidgetTestApp(data=None)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            assert widget is not None
            # Should show "No memory data available" label
            no_data_label = widget.query_one("#no-data", Label)
            assert no_data_label is not None

    @pytest.mark.asyncio
    async def test_memory_widget_renders_with_data(self) -> None:
        """Test that MemoryWidget renders correctly with data."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            assert widget is not None

    @pytest.mark.asyncio
    async def test_memory_widget_has_ram_section(self) -> None:
        """Test that MemoryWidget has RAM section."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            ram_bar = widget.query_one("#ram-bar", MemoryBar)
            assert ram_bar is not None
            assert ram_bar.label == "RAM"

    @pytest.mark.asyncio
    async def test_memory_widget_has_swap_section(self) -> None:
        """Test that MemoryWidget has Swap section."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            swap_bar = widget.query_one("#swap-bar", MemoryBar)
            assert swap_bar is not None
            assert swap_bar.label == "Swap"

    @pytest.mark.asyncio
    async def test_memory_widget_ram_percent(self) -> None:
        """Test that RAM bar shows correct percentage."""
        data = create_sample_memory_data(ram_percent=75.5)
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            ram_bar = widget.query_one("#ram-bar", MemoryBar)
            assert ram_bar.percent == 75.5

    @pytest.mark.asyncio
    async def test_memory_widget_swap_percent(self) -> None:
        """Test that Swap bar shows correct percentage."""
        data = create_sample_memory_data(swap_percent=30.0)
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            swap_bar = widget.query_one("#swap-bar", MemoryBar)
            assert swap_bar.percent == 30.0

    @pytest.mark.asyncio
    async def test_memory_widget_update_data(self) -> None:
        """Test that update_data method works correctly."""
        initial_data = create_sample_memory_data(ram_percent=50.0)
        app = MemoryWidgetTestApp(data=initial_data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)

            # Update with new data
            new_data = create_sample_memory_data(ram_percent=80.0)
            widget.update_data(new_data)
            await pilot.pause()

            assert widget.data is not None
            assert widget.data.virtual.percent == 80.0


class TestMemoryWidgetRamDetails:
    """Tests for RAM details in MemoryWidget."""

    def test_get_ram_details_basic(self) -> None:
        """Test _get_ram_details returns correct basic details."""
        data = create_sample_memory_data(
            ram_total=16 * 1024**3,
            ram_used=8 * 1024**3,
            ram_available=8 * 1024**3,
        )
        widget = MemoryWidget(data=data)
        details = widget._get_ram_details()

        labels = [label for label, _ in details]
        assert "Total" in labels
        assert "Used" in labels
        assert "Free" in labels
        assert "Available" in labels

    def test_get_ram_details_with_cached(self) -> None:
        """Test _get_ram_details includes cached when available."""
        data = create_sample_memory_data(ram_cached=2 * 1024**3)
        widget = MemoryWidget(data=data)
        details = widget._get_ram_details()

        labels = [label for label, _ in details]
        assert "Cached" in labels

    def test_get_ram_details_with_buffers(self) -> None:
        """Test _get_ram_details includes buffers when available."""
        data = create_sample_memory_data(ram_buffers=500 * 1024**2)
        widget = MemoryWidget(data=data)
        details = widget._get_ram_details()

        labels = [label for label, _ in details]
        assert "Buffers" in labels

    def test_get_ram_details_without_optional(self) -> None:
        """Test _get_ram_details excludes optional fields when None."""
        data = create_sample_memory_data(ram_cached=None, ram_buffers=None)
        widget = MemoryWidget(data=data)
        details = widget._get_ram_details()

        labels = [label for label, _ in details]
        assert "Cached" not in labels
        assert "Buffers" not in labels

    def test_get_ram_details_no_data(self) -> None:
        """Test _get_ram_details returns empty list when no data."""
        widget = MemoryWidget(data=None)
        details = widget._get_ram_details()
        assert details == []


class TestMemoryWidgetSwapDetails:
    """Tests for Swap details in MemoryWidget."""

    def test_get_swap_details_basic(self) -> None:
        """Test _get_swap_details returns correct basic details."""
        data = create_sample_memory_data(
            swap_total=8 * 1024**3,
            swap_used=2 * 1024**3,
            swap_free=6 * 1024**3,
        )
        widget = MemoryWidget(data=data)
        details = widget._get_swap_details()

        labels = [label for label, _ in details]
        assert "Total" in labels
        assert "Used" in labels
        assert "Free" in labels

    def test_get_swap_details_not_configured(self) -> None:
        """Test _get_swap_details shows 'Not configured' when swap total is 0."""
        data = create_sample_memory_data(
            swap_total=0,
            swap_used=0,
            swap_free=0,
        )
        widget = MemoryWidget(data=data)
        details = widget._get_swap_details()

        assert len(details) == 1
        assert details[0] == ("Status", "Not configured")

    def test_get_swap_details_no_data(self) -> None:
        """Test _get_swap_details returns empty list when no data."""
        widget = MemoryWidget(data=None)
        details = widget._get_swap_details()
        assert details == []


class TestMemoryWidgetCSS:
    """Tests for MemoryWidget CSS styling."""

    def test_memory_widget_has_default_css(self) -> None:
        """Test that MemoryWidget has default CSS defined."""
        assert MemoryWidget.DEFAULT_CSS is not None
        assert "MemoryWidget" in MemoryWidget.DEFAULT_CSS

    def test_memory_bar_has_default_css(self) -> None:
        """Test that MemoryBar has default CSS defined."""
        assert MemoryBar.DEFAULT_CSS is not None
        assert "MemoryBar" in MemoryBar.DEFAULT_CSS
        assert "medium" in MemoryBar.DEFAULT_CSS
        assert "high" in MemoryBar.DEFAULT_CSS

    def test_memory_details_has_default_css(self) -> None:
        """Test that MemoryDetails has default CSS defined."""
        assert MemoryDetails.DEFAULT_CSS is not None
        assert "MemoryDetails" in MemoryDetails.DEFAULT_CSS
