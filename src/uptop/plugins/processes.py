"""Process Pane Plugin for uptop.

This module provides the Process pane that displays system process information.
It collects process data using psutil and renders it in the TUI.

All process metrics are gauges (current values that can go up/down).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import psutil
from pydantic import ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import DisplayMode, MetricData, gauge_field
from uptop.plugin_api.base import PanePlugin

# Try to import Mojo bridge for performance optimization
try:
    from uptop.mojo_bridge import collect_top_processes_mojo, is_mojo_available
    MOJO_OPTIMIZATION_AVAILABLE = is_mojo_available()
except ImportError:
    MOJO_OPTIMIZATION_AVAILABLE = False
    collect_top_processes_mojo = None  # type: ignore

logger = logging.getLogger(__name__)

# Check environment variable for Mojo optimization
USE_MOJO_BY_DEFAULT = os.environ.get("UPTOP_USE_MOJO", "false").lower() in ("true", "1", "yes")

if TYPE_CHECKING:
    from textual.widget import Widget


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class ProcessInfo(MetricData):
    """Information about a single process.

    All resource usage fields are gauges representing current values.

    Attributes:
        pid: Process ID
        name: Process name
        username: Username of the process owner
        cpu_percent: CPU usage percentage (0-100+) [gauge]
        memory_percent: Memory usage percentage (0-100) [gauge]
        memory_rss_bytes: Resident Set Size in bytes [gauge]
        memory_vms_bytes: Virtual Memory Size in bytes [gauge]
        status: Process status (running, sleeping, etc.)
        create_time: Unix timestamp of process creation
        cmdline: Full command line (optional, may be None if access denied)
        num_threads: Number of threads in the process [gauge]
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pid: int = Field(..., ge=0, description="Process ID")
    name: str = Field(..., min_length=0, description="Process name")
    username: str = Field(default="", description="Username of process owner")
    cpu_percent: float = gauge_field("CPU usage percentage", default=0.0, ge=0.0)
    memory_percent: float = gauge_field("Memory usage percentage", default=0.0, ge=0.0, le=100.0)
    memory_rss_bytes: int = gauge_field("Resident Set Size in bytes", default=0, ge=0)
    memory_vms_bytes: int = gauge_field("Virtual Memory Size in bytes", default=0, ge=0)
    status: str = Field(default="unknown", description="Process status")
    create_time: float = Field(default=0.0, ge=0.0, description="Unix timestamp of creation")
    cmdline: str | None = Field(default=None, description="Full command line")
    num_threads: int = gauge_field("Number of threads", default=1, ge=0)


class ProcessListData(MetricData):
    """Data model for process list pane.

    Aggregates process information for display in the TUI.

    Attributes:
        processes: List of ProcessInfo objects
        total_count: Total number of processes [gauge]
        running_count: Number of running processes [gauge]
    """

    processes: list[ProcessInfo] = Field(default_factory=list, description="List of processes")
    total_count: int = gauge_field("Total number of processes", default=0, ge=0)
    running_count: int = gauge_field("Number of running processes", default=0, ge=0)


class ProcessCollector(DataCollector[ProcessListData]):
    """Collector for system process information.

    Uses psutil to gather process data efficiently. Handles AccessDenied
    and NoSuchProcess exceptions gracefully by filtering out inaccessible
    processes.

    Class Attributes:
        name: Unique identifier for this collector
        default_interval: Default collection interval (2.0 seconds)
        timeout: Maximum time allowed for a single collection
    """

    name = "process_collector"
    default_interval = 2.0
    timeout = 10.0

    # Process attributes to collect via psutil
    PROCESS_ATTRS = [
        "pid",
        "name",
        "username",
        "cpu_percent",
        "memory_percent",
        "memory_info",
        "status",
        "create_time",
        "cmdline",
        "num_threads",
    ]
    
    def __init__(self, use_mojo: bool | None = None, max_processes: int = 100) -> None:
        """Initialize the process collector.
        
        Args:
            use_mojo: Use Mojo optimization if available (experimental).
                     If None, uses UPTOP_USE_MOJO environment variable.
            max_processes: Maximum number of processes to collect (default: 100)
        """
        super().__init__()
        
        # Use environment variable if not explicitly set
        if use_mojo is None:
            use_mojo = USE_MOJO_BY_DEFAULT
        
        self.use_mojo = use_mojo and MOJO_OPTIMIZATION_AVAILABLE
        self.max_processes = max_processes
        
        if use_mojo and not MOJO_OPTIMIZATION_AVAILABLE:
            logger.warning(
                "Mojo optimization requested but not available. "
                "Falling back to Python implementation."
            )
        elif self.use_mojo:
            logger.info(
                f"Using Mojo optimization for process collection (max {max_processes} processes)"
            )

    async def collect(self) -> ProcessListData:
        """Collect current process data.

        Returns:
            ProcessListData with current process information

        Note:
            Processes that cannot be accessed (AccessDenied, NoSuchProcess)
            are silently filtered out.
            
            If use_mojo is enabled and available, uses fast Mojo implementation.
        """
        # Try Mojo optimization first
        if self.use_mojo and collect_top_processes_mojo is not None:
            try:
                mojo_data = collect_top_processes_mojo(self.max_processes)
                # Convert Mojo result to ProcessInfo objects
                processes = [
                    ProcessInfo(
                        pid=p["pid"],
                        name=p["name"],
                        username=p["username"],
                        cpu_percent=p["cpu_percent"],
                        memory_percent=p["memory_percent"],
                        memory_rss_bytes=p["memory_rss_bytes"],
                        memory_vms_bytes=p["memory_vms_bytes"],
                        status=p["status"],
                        create_time=p["create_time"],
                        cmdline=p["cmdline"],
                        num_threads=p["num_threads"],
                        source=self.name,
                    )
                    for p in mojo_data["processes"]
                ]
                return ProcessListData(
                    processes=processes,
                    total_count=mojo_data["total_count"],
                    running_count=mojo_data["running_count"],
                    source=self.name,
                )
            except NotImplementedError:
                # Mojo integration not fully ready, fall back
                logger.debug("Mojo optimization not ready, using Python fallback")
            except Exception as e:
                logger.warning(f"Mojo optimization failed: {e}, using Python fallback")
        
        # Python implementation
        processes: list[ProcessInfo] = []
        running_count = 0

        for proc in psutil.process_iter(attrs=self.PROCESS_ATTRS):
            try:
                info = proc.info
                if info is None:
                    continue

                # Extract memory info
                memory_info = info.get("memory_info")
                rss = 0
                vms = 0
                if memory_info is not None:
                    rss = getattr(memory_info, "rss", 0) or 0
                    vms = getattr(memory_info, "vms", 0) or 0

                # Handle cmdline - it may be a list or None
                cmdline_raw = info.get("cmdline")
                cmdline = None
                if cmdline_raw is not None:
                    if isinstance(cmdline_raw, list):
                        cmdline = " ".join(cmdline_raw) if cmdline_raw else None
                    else:
                        cmdline = str(cmdline_raw)

                # Get status and count running processes
                status = info.get("status", "unknown") or "unknown"
                if status == psutil.STATUS_RUNNING:
                    running_count += 1

                process_info = ProcessInfo(
                    pid=info.get("pid", 0) or 0,
                    name=info.get("name", "") or "",
                    username=info.get("username", "") or "",
                    cpu_percent=info.get("cpu_percent", 0.0) or 0.0,
                    memory_percent=info.get("memory_percent", 0.0) or 0.0,
                    memory_rss_bytes=rss,
                    memory_vms_bytes=vms,
                    status=status,
                    create_time=info.get("create_time", 0.0) or 0.0,
                    cmdline=cmdline,
                    num_threads=info.get("num_threads", 1) or 1,
                    source=self.name,
                )
                processes.append(process_info)

            except (psutil.AccessDenied, psutil.NoSuchProcess):
                # Process went away or we don't have permission - skip it
                continue
            except (psutil.ZombieProcess, AttributeError):
                # Zombie process or attribute error - skip it
                continue

        return ProcessListData(
            processes=processes,
            total_count=len(processes),
            running_count=running_count,
            source=self.name,
        )

    def get_schema(self) -> type[ProcessListData]:
        """Return the Pydantic model class for this collector's data.

        Returns:
            ProcessListData class
        """
        return ProcessListData


class ProcessPane(PanePlugin):
    """Process monitoring pane plugin.

    Displays a list of system processes with their resource usage.
    Supports sorting, filtering, and actions like kill/renice.

    Class Attributes:
        name: Plugin identifier
        display_name: Human-readable name
        version: Plugin version
        description: Brief description
        default_refresh_interval: Update interval (2.0 seconds)
    """

    name = "processes"
    display_name = "Processes"
    version = "0.1.0"
    description = "Displays system processes with CPU, memory, and status information"
    author = "uptop"
    default_refresh_interval = 2.0

    def __init__(self) -> None:
        """Initialize the ProcessPane."""
        super().__init__()
        self._collector = ProcessCollector()
        self._cached_widget = None  # Cache widget to preserve filter/sort state

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the pane with configuration.

        Args:
            config: Plugin-specific configuration
        """
        super().initialize(config)
        self._collector.initialize(config)

    def shutdown(self) -> None:
        """Clean up resources."""
        self._cached_widget = None
        self._collector.shutdown()
        super().shutdown()

    async def collect_data(self) -> ProcessListData:
        """Collect current process data.

        Returns:
            ProcessListData with current process information
        """
        return await self._collector.collect()

    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> Widget:
        """Render the process data as a Textual widget.

        Args:
            data: ProcessListData from collect_data()
            size: Optional (width, height) in cells (currently unused)
            mode: Optional DisplayMode (currently unused, always full display)

        Returns:
            A Textual Widget for display
        """
        # Import here to avoid circular imports and allow testing without textual
        from textual.widgets import Label

        from uptop.tui.panes.process_widget import ProcessWidget

        if not isinstance(data, ProcessListData):
            return Label("Invalid data type")

        # Reuse cached widget to preserve filter/sort state
        if self._cached_widget is None:
            self._cached_widget = ProcessWidget()
        self._cached_widget.update_data(data, mode)
        return self._cached_widget

    def get_schema(self) -> type[ProcessListData]:
        """Return the Pydantic model class for this pane's data.

        Returns:
            ProcessListData class
        """
        return ProcessListData
