"""Memory pane plugin for uptop.

This module provides the memory monitoring pane that displays RAM and swap usage.
It includes:
- VirtualMemory model for RAM metrics
- SwapMemory model for swap/page file metrics
- MemoryData aggregated model
- MemoryCollector for gathering metrics via psutil
- MemoryPane plugin for TUI display

All memory metrics are gauges (current values that can go up/down).
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import psutil
from pydantic import BaseModel, ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import DisplayMode, MetricData, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget


# Cache total memory - it doesn't change during runtime
@lru_cache(maxsize=1)
def _get_total_memory() -> int:
    """Get total system memory in bytes (cached)."""
    return psutil.virtual_memory().total


class VirtualMemory(BaseModel):
    """Model for virtual (RAM) memory statistics.

    All fields are gauges representing current memory state.

    Attributes:
        total_bytes: Total physical memory in bytes [gauge]
        used_bytes: Memory used by processes [gauge]
        available_bytes: Memory available for new processes without swapping [gauge]
        percent: Percentage of memory used (used / total * 100) [gauge]
        cached_bytes: Memory used for disk cache (Linux/macOS only) [gauge]
        buffers_bytes: Memory used for filesystem buffers (Linux only) [gauge]
        active_bytes: Memory currently in use or recently used (Linux/macOS) [gauge]
        inactive_bytes: Memory marked as not used (Linux/macOS) [gauge]
    """

    # Use frozen=True for immutability
    model_config = ConfigDict(frozen=True)

    total_bytes: int = gauge_field("Total physical memory in bytes", ge=0)
    used_bytes: int = gauge_field("Used memory in bytes", ge=0)
    available_bytes: int = gauge_field("Available memory in bytes", ge=0)
    percent: float = gauge_field("Memory usage percentage", ge=0.0, le=100.0)
    cached_bytes: int | None = gauge_field(
        "Cached memory in bytes (Linux/macOS)", default=None, ge=0
    )
    buffers_bytes: int | None = gauge_field("Buffer memory in bytes (Linux)", default=None, ge=0)
    active_bytes: int | None = gauge_field(
        "Active memory in bytes (Linux/macOS)", default=None, ge=0
    )
    inactive_bytes: int | None = gauge_field(
        "Inactive memory in bytes (Linux/macOS)", default=None, ge=0
    )

    @property
    def free_bytes(self) -> int:
        """Calculate free memory (total - used)."""
        return self.total_bytes - self.used_bytes


class SwapMemory(BaseModel):
    """Model for swap memory statistics.

    All fields are gauges representing current swap state.

    Attributes:
        total_bytes: Total swap space in bytes [gauge]
        used_bytes: Used swap space in bytes [gauge]
        free_bytes: Free swap space in bytes [gauge]
        percent: Percentage of swap used [gauge]
    """

    # Use frozen=True for immutability
    model_config = ConfigDict(frozen=True)

    total_bytes: int = gauge_field("Total swap space in bytes", ge=0)
    used_bytes: int = gauge_field("Used swap space in bytes", ge=0)
    free_bytes: int = gauge_field("Free swap space in bytes", ge=0)
    percent: float = gauge_field("Swap usage percentage", ge=0.0, le=100.0)


class MemoryData(MetricData):
    """Aggregated memory data model.

    Contains both virtual memory (RAM) and swap statistics.

    Attributes:
        virtual: Virtual memory (RAM) statistics
        swap: Swap memory statistics
    """

    virtual: VirtualMemory = Field(..., description="Virtual memory statistics")
    swap: SwapMemory = Field(..., description="Swap memory statistics")


class MemoryCollector(DataCollector[MemoryData]):
    """Collector for memory metrics using psutil.

    Gathers both virtual memory (RAM) and swap usage statistics.
    Handles platform differences gracefully - cached and buffers may
    not be available on all platforms.
    """

    name: str = "memory"
    default_interval: float = 2.0
    timeout: float = 5.0

    async def collect(self) -> MemoryData:
        """Collect current memory statistics.

        Returns:
            MemoryData containing virtual and swap memory stats

        Raises:
            Exception: If psutil fails to retrieve memory info
        """
        # Collect virtual memory
        vm = psutil.virtual_memory()

        # Handle platform differences - cached, buffers, active, inactive may not exist
        cached_bytes: int | None = getattr(vm, "cached", None)
        buffers_bytes: int | None = getattr(vm, "buffers", None)
        active_bytes: int | None = getattr(vm, "active", None)
        inactive_bytes: int | None = getattr(vm, "inactive", None)

        virtual = VirtualMemory(
            total_bytes=vm.total,
            used_bytes=vm.used,
            available_bytes=vm.available,
            percent=vm.percent,
            cached_bytes=cached_bytes,
            buffers_bytes=buffers_bytes,
            active_bytes=active_bytes,
            inactive_bytes=inactive_bytes,
        )

        # Collect swap memory
        sm = psutil.swap_memory()

        swap = SwapMemory(
            total_bytes=sm.total,
            used_bytes=sm.used,
            free_bytes=sm.free,
            percent=sm.percent,
        )

        return MemoryData(
            virtual=virtual,
            swap=swap,
            source="memory",
        )

    def get_schema(self) -> type[MemoryData]:
        """Return the MemoryData model class.

        Returns:
            The MemoryData Pydantic model class
        """
        return MemoryData


class MemoryPane(PanePlugin):
    """Memory monitoring pane plugin.

    Displays RAM and swap usage in the TUI. Shows:
    - Total, used, available, and cached memory
    - Swap usage statistics
    - Usage percentages with visual indicators
    """

    name: str = "memory"
    display_name: str = "Memory & Swap"
    version: str = "0.1.0"
    description: str = "Monitor RAM and swap memory usage"
    author: str = "uptop"
    default_refresh_interval: float = 2.0

    def __init__(self) -> None:
        """Initialize the memory pane."""
        super().__init__()
        self._collector = MemoryCollector()
        self._cached_widget = None  # Cache widget to preserve sparkline history

    async def collect_data(self) -> MemoryData:
        """Collect current memory metrics.

        Returns:
            MemoryData with current virtual and swap statistics
        """
        return await self._collector.collect()

    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> "Widget":
        """Render memory data as a Textual widget.

        Caches the widget instance to preserve sparkline history across refreshes.

        Args:
            data: The MemoryData from collect_data()
            size: Optional (width, height) in cells (currently unused)
            mode: Optional DisplayMode (currently unused, always full display)

        Returns:
            A Textual widget displaying memory information
        """
        from textual.widgets import Label

        from uptop.tui.panes.memory_widget import MemoryWidget

        # Type check for mypy
        if not isinstance(data, MemoryData):
            return Label("Invalid data type for MemoryPane")

        # Reuse cached widget to preserve sparkline history
        if self._cached_widget is None:
            self._cached_widget = MemoryWidget()

        self._cached_widget.update_data(data, mode)
        return self._cached_widget

    def get_schema(self) -> type[MemoryData]:
        """Return the MemoryData model class.

        Returns:
            The MemoryData Pydantic model class
        """
        return MemoryData
