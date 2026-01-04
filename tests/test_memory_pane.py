"""Tests for the Memory pane plugin."""

from collections import namedtuple
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
import pytest

from uptop.models import MetricData, MetricType, PluginType, get_metric_type
from uptop.plugins.memory import (
    MemoryCollector,
    MemoryData,
    MemoryPane,
    SwapMemory,
    VirtualMemory,
)

# Mock psutil types
MockVirtualMemory = namedtuple(
    "svmem", ["total", "used", "available", "percent", "cached", "buffers"]
)
MockSwapMemory = namedtuple("sswap", ["total", "used", "free", "percent"])


# ============================================================================
# VirtualMemory Model Tests
# ============================================================================


class TestVirtualMemory:
    """Tests for VirtualMemory model."""

    def test_valid_virtual_memory(self) -> None:
        """Test creating valid virtual memory."""
        vm = VirtualMemory(
            total_bytes=16000000000,
            used_bytes=8000000000,
            available_bytes=8000000000,
            percent=50.0,
            cached_bytes=2000000000,
            buffers_bytes=500000000,
        )

        assert vm.total_bytes == 16000000000
        assert vm.used_bytes == 8000000000
        assert vm.available_bytes == 8000000000
        assert vm.percent == 50.0
        assert vm.cached_bytes == 2000000000
        assert vm.buffers_bytes == 500000000

    def test_virtual_memory_optional_fields(self) -> None:
        """Test that cached_bytes and buffers_bytes are optional."""
        vm = VirtualMemory(
            total_bytes=16000000000,
            used_bytes=8000000000,
            available_bytes=8000000000,
            percent=50.0,
        )

        assert vm.cached_bytes is None
        assert vm.buffers_bytes is None

    def test_virtual_memory_free_bytes_property(self) -> None:
        """Test free_bytes calculated property."""
        vm = VirtualMemory(
            total_bytes=16000000000,
            used_bytes=8000000000,
            available_bytes=6000000000,
            percent=50.0,
        )

        assert vm.free_bytes == 8000000000  # total - used

    def test_virtual_memory_negative_bytes_invalid(self) -> None:
        """Test that negative byte values are rejected."""
        with pytest.raises(ValidationError):
            VirtualMemory(
                total_bytes=-16000000000,
                used_bytes=8000000000,
                available_bytes=8000000000,
                percent=50.0,
            )

    def test_virtual_memory_percent_out_of_range(self) -> None:
        """Test that percent outside 0-100 is rejected."""
        with pytest.raises(ValidationError):
            VirtualMemory(
                total_bytes=16000000000,
                used_bytes=8000000000,
                available_bytes=8000000000,
                percent=150.0,
            )

        with pytest.raises(ValidationError):
            VirtualMemory(
                total_bytes=16000000000,
                used_bytes=8000000000,
                available_bytes=8000000000,
                percent=-10.0,
            )


# ============================================================================
# SwapMemory Model Tests
# ============================================================================


class TestSwapMemory:
    """Tests for SwapMemory model."""

    def test_valid_swap_memory(self) -> None:
        """Test creating valid swap memory."""
        sm = SwapMemory(
            total_bytes=8000000000,
            used_bytes=2000000000,
            free_bytes=6000000000,
            percent=25.0,
        )

        assert sm.total_bytes == 8000000000
        assert sm.used_bytes == 2000000000
        assert sm.free_bytes == 6000000000
        assert sm.percent == 25.0

    def test_swap_memory_zero_values(self) -> None:
        """Test swap with zero values (no swap configured)."""
        sm = SwapMemory(
            total_bytes=0,
            used_bytes=0,
            free_bytes=0,
            percent=0.0,
        )

        assert sm.total_bytes == 0
        assert sm.used_bytes == 0
        assert sm.free_bytes == 0
        assert sm.percent == 0.0

    def test_swap_memory_negative_bytes_invalid(self) -> None:
        """Test that negative byte values are rejected."""
        with pytest.raises(ValidationError):
            SwapMemory(
                total_bytes=8000000000,
                used_bytes=-2000000000,
                free_bytes=6000000000,
                percent=25.0,
            )

    def test_swap_memory_percent_out_of_range(self) -> None:
        """Test that percent outside 0-100 is rejected."""
        with pytest.raises(ValidationError):
            SwapMemory(
                total_bytes=8000000000,
                used_bytes=2000000000,
                free_bytes=6000000000,
                percent=150.0,
            )


# ============================================================================
# MemoryData Model Tests
# ============================================================================


class TestMemoryData:
    """Tests for MemoryData model."""

    def test_memory_data_creation(self) -> None:
        """Test MemoryData creation with nested models."""
        virtual = VirtualMemory(
            total_bytes=16000000000,
            used_bytes=8000000000,
            available_bytes=8000000000,
            percent=50.0,
        )
        swap = SwapMemory(
            total_bytes=8000000000,
            used_bytes=2000000000,
            free_bytes=6000000000,
            percent=25.0,
        )

        data = MemoryData(virtual=virtual, swap=swap, source="memory")

        assert data.virtual.total_bytes == 16000000000
        assert data.swap.total_bytes == 8000000000
        assert data.source == "memory"

    def test_memory_data_inherits_metric_data(self) -> None:
        """Test that MemoryData inherits from MetricData."""
        virtual = VirtualMemory(
            total_bytes=16000000000,
            used_bytes=8000000000,
            available_bytes=8000000000,
            percent=50.0,
        )
        swap = SwapMemory(
            total_bytes=8000000000,
            used_bytes=2000000000,
            free_bytes=6000000000,
            percent=25.0,
        )

        data = MemoryData(virtual=virtual, swap=swap)
        assert isinstance(data, MetricData)


# ============================================================================
# Metric Type Tests
# ============================================================================


class TestMemoryMetricTypes:
    """Tests for metric type annotations on Memory models."""

    def test_virtual_memory_metric_types(self) -> None:
        """Test that VirtualMemory fields have correct metric types."""
        assert get_metric_type(VirtualMemory, "total_bytes") == MetricType.GAUGE
        assert get_metric_type(VirtualMemory, "used_bytes") == MetricType.GAUGE
        assert get_metric_type(VirtualMemory, "available_bytes") == MetricType.GAUGE
        assert get_metric_type(VirtualMemory, "percent") == MetricType.GAUGE
        assert get_metric_type(VirtualMemory, "cached_bytes") == MetricType.GAUGE
        assert get_metric_type(VirtualMemory, "buffers_bytes") == MetricType.GAUGE

    def test_swap_memory_metric_types(self) -> None:
        """Test that SwapMemory fields have correct metric types."""
        assert get_metric_type(SwapMemory, "total_bytes") == MetricType.GAUGE
        assert get_metric_type(SwapMemory, "used_bytes") == MetricType.GAUGE
        assert get_metric_type(SwapMemory, "free_bytes") == MetricType.GAUGE
        assert get_metric_type(SwapMemory, "percent") == MetricType.GAUGE


# ============================================================================
# MemoryCollector Tests
# ============================================================================


class TestMemoryCollector:
    """Tests for MemoryCollector."""

    def test_collector_attributes(self) -> None:
        """Test collector class attributes."""
        collector = MemoryCollector()

        assert collector.name == "memory"
        assert collector.default_interval == 2.0
        assert collector.timeout == 5.0

    @pytest.mark.asyncio
    @patch("uptop.plugins.memory.psutil.virtual_memory")
    @patch("uptop.plugins.memory.psutil.swap_memory")
    async def test_collect_success(
        self,
        mock_swap: MagicMock,
        mock_virtual: MagicMock,
    ) -> None:
        """Test successful collection."""
        mock_virtual.return_value = MockVirtualMemory(
            total=16000000000,
            used=8000000000,
            available=8000000000,
            percent=50.0,
            cached=2000000000,
            buffers=500000000,
        )
        mock_swap.return_value = MockSwapMemory(
            total=8000000000,
            used=2000000000,
            free=6000000000,
            percent=25.0,
        )

        collector = MemoryCollector()
        data = await collector.collect()

        assert isinstance(data, MemoryData)
        assert data.source == "memory"
        assert data.virtual.total_bytes == 16000000000

    @pytest.mark.asyncio
    @patch("uptop.plugins.memory.psutil.virtual_memory")
    @patch("uptop.plugins.memory.psutil.swap_memory")
    async def test_collect_no_swap(
        self,
        mock_swap: MagicMock,
        mock_virtual: MagicMock,
    ) -> None:
        """Test collection when no swap is configured."""
        mock_virtual.return_value = MockVirtualMemory(
            total=16000000000,
            used=8000000000,
            available=8000000000,
            percent=50.0,
            cached=2000000000,
            buffers=500000000,
        )
        mock_swap.return_value = MockSwapMemory(
            total=0,
            used=0,
            free=0,
            percent=0.0,
        )

        collector = MemoryCollector()
        data = await collector.collect()

        assert data.swap.total_bytes == 0

    def test_get_schema(self) -> None:
        """Test get_schema returns MemoryData."""
        collector = MemoryCollector()
        assert collector.get_schema() == MemoryData


# ============================================================================
# MemoryPane Tests
# ============================================================================


class TestMemoryPane:
    """Tests for MemoryPane plugin."""

    def test_pane_attributes(self) -> None:
        """Test pane class attributes."""
        pane = MemoryPane()

        assert pane.name == "memory"
        assert pane.display_name == "Memory & Swap"
        assert pane.default_refresh_interval == 2.0

    def test_pane_plugin_type(self) -> None:
        """Test that MemoryPane returns PANE plugin type."""
        assert MemoryPane.get_plugin_type() == PluginType.PANE

    def test_pane_has_collector(self) -> None:
        """Test that pane creates a collector."""
        pane = MemoryPane()
        assert isinstance(pane._collector, MemoryCollector)

    def test_render_tui_valid_data(self) -> None:
        """Test render_tui with valid data."""
        pane = MemoryPane()

        virtual = VirtualMemory(
            total_bytes=16000000000,
            used_bytes=8000000000,
            available_bytes=8000000000,
            percent=50.0,
        )
        swap = SwapMemory(
            total_bytes=8000000000,
            used_bytes=2000000000,
            free_bytes=6000000000,
            percent=25.0,
        )

        data = MemoryData(virtual=virtual, swap=swap)
        widget = pane.render_tui(data)

        from uptop.tui.panes.memory_widget import MemoryWidget

        assert isinstance(widget, MemoryWidget)
        assert hasattr(widget, "update_data")

    def test_render_tui_invalid_data(self) -> None:
        """Test render_tui with invalid data type."""
        pane = MemoryPane()
        data = MetricData()
        widget = pane.render_tui(data)

        from textual.widgets import Label

        assert isinstance(widget, Label)

    def test_get_schema(self) -> None:
        """Test get_schema returns MemoryData."""
        pane = MemoryPane()
        assert pane.get_schema() == MemoryData

    def test_get_metadata(self) -> None:
        """Test metadata generation."""
        meta = MemoryPane.get_metadata()

        assert meta.name == "memory"
        assert meta.display_name == "Memory & Swap"
        assert meta.plugin_type == PluginType.PANE

    def test_initialize_and_shutdown(self) -> None:
        """Test plugin lifecycle methods."""
        pane = MemoryPane()

        pane.initialize({"custom_setting": "value"})
        assert pane._initialized is True

        pane.shutdown()
        assert pane._initialized is False
