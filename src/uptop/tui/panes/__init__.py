"""Pane widgets for uptop TUI.

This module provides pane widgets that display metric data:
- CPUWidget: CPU usage, load averages, frequency, and temperature display
- DiskWidget: Disk partition usage and I/O statistics display
- MemoryWidget: RAM and Swap usage with progress bars and details
- NetworkWidget: Network interface statistics and connections display
- ProcessWidget: Process list with DataTable for monitoring system processes
"""

# ruff: noqa: I001
from uptop.tui.panes.cpu_widget import (
    THRESHOLD_LOW,
    THRESHOLD_MEDIUM,
    CoreUsageRow,
    CPUProgressBar,
    CPUWidget,
    get_usage_color,
    get_usage_style,
)
from uptop.tui.panes.disk_widget import (
    DiskWidget,
    IOStatsDisplay,
    PartitionDisplay,
    format_bytes,
    format_rate,
)
from uptop.tui.panes.disk_widget import get_usage_color as get_disk_usage_color
from uptop.tui.panes.memory_widget import (
    MemoryBar,
    MemoryDetails,
    MemoryWidget,
)
from uptop.tui.panes.memory_widget import format_bytes as format_memory_bytes
from uptop.tui.panes.memory_widget import get_usage_color as get_memory_usage_color
from uptop.tui.panes.network_widget import NetworkWidget
from uptop.tui.panes.process_widget import (
    COLUMN_CONFIG,
    ProcessColumn,
    ProcessWidget,
    SortDirection,
)
from uptop.tui.panes.process_widget import format_bytes as format_process_bytes
from uptop.tui.panes.process_widget import (
    format_runtime,
    truncate_command,
)

__all__ = [
    # CPU Widget
    "CPUWidget",
    "CoreUsageRow",
    "CPUProgressBar",
    "get_usage_color",
    "get_usage_style",
    "THRESHOLD_LOW",
    "THRESHOLD_MEDIUM",
    # Disk Widget
    "DiskWidget",
    "IOStatsDisplay",
    "PartitionDisplay",
    "format_bytes",
    "format_rate",
    "get_disk_usage_color",
    # Memory Widget
    "MemoryWidget",
    "MemoryBar",
    "MemoryDetails",
    "format_memory_bytes",
    "get_memory_usage_color",
    # Network Widget
    "NetworkWidget",
    # Process Widget
    "ProcessWidget",
    "ProcessColumn",
    "SortDirection",
    "COLUMN_CONFIG",
    "format_process_bytes",
    "format_runtime",
    "truncate_command",
]
