"""Tests for the Memory Widget.

This module tests the MemoryWidget functionality including:
- Widget instantiation
- Rendering with sample MemoryData
- Size formatting utilities
- RAM and Swap display in table format
"""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from uptop.plugins.memory import MemoryData, SwapMemory, VirtualMemory
from uptop.tui.panes.memory_widget import (
    MemoryWidget,
    format_bytes,
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
        """Test formatting zero bytes (still shows as KB)."""
        assert format_bytes(0) == "0.0KB"

    def test_format_bytes_small(self) -> None:
        """Test formatting small byte values (converted to KB)."""
        # Small values are converted to KB (no plain bytes)
        assert format_bytes(100) == "0.1KB"
        assert format_bytes(1023) == "1.0KB"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobyte values."""
        assert format_bytes(1024) == "1.0KB"
        assert format_bytes(1536) == "1.5KB"
        assert format_bytes(10240) == "10.0KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabyte values."""
        assert format_bytes(1024 * 1024) == "1.0MB"
        assert format_bytes(512 * 1024 * 1024) == "512.0MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabyte values."""
        assert format_bytes(1024**3) == "1.0GB"
        assert format_bytes(16 * 1024**3) == "16.0GB"

    def test_format_bytes_terabytes(self) -> None:
        """Test formatting terabyte values."""
        assert format_bytes(1024**4) == "1.0TB"
        assert format_bytes(2 * 1024**4) == "2.0TB"

    def test_format_bytes_petabytes(self) -> None:
        """Test formatting petabyte values."""
        assert format_bytes(1024**5) == "1.0PB"


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
    async def test_memory_widget_renders_with_data(self) -> None:
        """Test that MemoryWidget renders correctly with data."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            assert widget is not None

    @pytest.mark.asyncio
    async def test_memory_widget_has_data_table(self) -> None:
        """Test that MemoryWidget has a DataTable for stats."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            table = widget.query_one("#memory-table", DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_memory_widget_table_has_columns(self) -> None:
        """Test that the DataTable has P-MEM, P-MAX, V-MEM, V-MAX columns."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            table = widget.query_one("#memory-table", DataTable)
            # Table should have 5 columns: metric, p_mem, p_max, v_mem, v_max
            assert len(table.columns) == 5

    @pytest.mark.asyncio
    async def test_memory_widget_table_has_rows(self) -> None:
        """Test that the DataTable has Total, Used, Free, Available rows."""
        data = create_sample_memory_data()
        app = MemoryWidgetTestApp(data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-widget", MemoryWidget)
            table = widget.query_one("#memory-table", DataTable)
            # Table should have 4 rows: Total, Used, Free, Available
            assert table.row_count == 4

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


class TestMemoryWidgetCSS:
    """Tests for MemoryWidget CSS styling."""

    def test_memory_widget_has_default_css(self) -> None:
        """Test that MemoryWidget has default CSS defined."""
        assert MemoryWidget.DEFAULT_CSS is not None
        assert "MemoryWidget" in MemoryWidget.DEFAULT_CSS
