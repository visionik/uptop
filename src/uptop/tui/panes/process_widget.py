"""Process Widget for uptop TUI.

This module provides a DataTable-based widget for displaying system processes
with columns for PID, User, CPU%, MEM%, VSZ, RSS, State, Runtime, and Command.

The widget supports:
- Sortable columns with stored sort state
- Process state coloring (R=green, S=gray, etc.)
- Highlighted high CPU/memory processes
- Truncated command display
- Selection tracking for actions like kill
- Sort cycling through columns with 's' key
- Process filtering by name/command/PID
- Tree view with parent-child relationships
- Mouse support: click to select rows, scroll wheel navigation
- Mouse-based column header sorting
"""

from __future__ import annotations

from enum import Enum
import platform
import subprocess
import time
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Label
from textual.widgets.data_table import RowKey

if TYPE_CHECKING:
    from uptop.plugins.processes import ProcessInfo, ProcessListData


def get_max_pid() -> int:
    """Get the maximum PID value for the current OS.

    Returns:
        Maximum PID value supported by the OS.
        - Linux: reads /proc/sys/kernel/pid_max (default 32768, max 4194304)
        - FreeBSD: reads sysctl kern.pid_max (typically 99999)
        - macOS: fixed at 99998
    """
    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/sys/kernel/pid_max") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return 32768  # Linux default

    if system == "FreeBSD":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "kern.pid_max"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        return 99999  # FreeBSD default

    if system == "Darwin":  # macOS
        return 99998

    # Unknown OS - use conservative default
    return 99999


def get_pid_column_width() -> int:
    """Calculate the PID column width based on max PID digits.

    Returns:
        Column width needed to display the largest possible PID.
    """
    max_pid = get_max_pid()
    return len(str(max_pid))


# Cache the PID column width at module load time
_PID_COLUMN_WIDTH = get_pid_column_width()


class SortDirection(str, Enum):
    """Sort direction for columns."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class ProcessColumn(str, Enum):
    """Available columns for process display."""

    PID = "pid"
    USER = "user"
    CPU = "cpu"
    MEM = "mem"
    VSZ = "vsz"
    RSS = "rss"
    STATE = "state"
    RUNTIME = "runtime"
    COMMAND = "command"


# Column metadata: (display_name, width, is_sortable)
# PID width is dynamically calculated based on OS max PID
COLUMN_CONFIG: dict[ProcessColumn, tuple[str, int | None, bool]] = {
    ProcessColumn.PID: ("PID", _PID_COLUMN_WIDTH, True),
    ProcessColumn.USER: ("User", 12, True),
    ProcessColumn.CPU: ("CPU%", 7, True),
    ProcessColumn.MEM: ("MEM%", 7, True),
    ProcessColumn.VSZ: ("V-MEM", 7, True),
    ProcessColumn.RSS: ("P-MEM", 7, True),
    ProcessColumn.STATE: ("⚑", 1, True),
    ProcessColumn.RUNTIME: ("Runtime", 10, True),
    ProcessColumn.COMMAND: ("Command", None, True),  # None = flexible width
}

# Sort cycling order: CPU% -> MEM% -> PID -> User -> Command -> (repeat)
SORT_CYCLE_ORDER: list[ProcessColumn] = [
    ProcessColumn.CPU,
    ProcessColumn.MEM,
    ProcessColumn.PID,
    ProcessColumn.USER,
    ProcessColumn.COMMAND,
]

# Process state display colors and symbols
STATE_STYLES: dict[str, tuple[str, str]] = {
    "running": ("R", "green"),
    "sleeping": ("S", "dim"),
    "disk-sleep": ("D", "yellow"),
    "stopped": ("T", "red"),
    "zombie": ("Z", "red bold"),
    "dead": ("X", "red dim"),
    "idle": ("I", "dim"),
    "waking": ("W", "cyan"),
    "parked": ("P", "dim"),
    "tracing-stop": ("t", "yellow"),
}


def format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.5G", "256M", "128K")
        Output is always <= 7 chars to fit column width.
    """
    if size_bytes < 0:
        return "0"

    units = [("T", 1024**4), ("G", 1024**3), ("M", 1024**2), ("K", 1024)]

    for suffix, threshold in units:
        if size_bytes >= threshold:
            value = size_bytes / threshold
            if value >= 100:
                return f"{int(value)}{suffix}"
            if value >= 10:
                return f"{value:.1f}{suffix}"
            return f"{value:.2f}{suffix}"

    return str(size_bytes)


def format_runtime(create_time: float) -> str:
    """Format process runtime as HH:MM:SS.

    Args:
        create_time: Unix timestamp of process creation

    Returns:
        Runtime string in HH:MM:SS format
    """
    if create_time <= 0:
        return "00:00:00"

    now = time.time()
    elapsed = max(0, now - create_time)

    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)

    if hours > 99:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_command(cmdline: str | None, name: str) -> str:
    """Format command line for display.

    Args:
        cmdline: Full command line or None
        name: Process name fallback

    Returns:
        Command string (full, not truncated - horizontal scroll handles overflow)
    """
    text = cmdline if cmdline else name
    if not text:
        return "<unknown>"
    return text


def truncate_command(cmdline: str | None, name: str, max_length: int = 50) -> str:
    """Format and truncate command line for display.

    Args:
        cmdline: Full command line or None
        name: Process name fallback
        max_length: Maximum length of the returned string

    Returns:
        Command string, truncated with "..." if exceeds max_length
    """
    text = cmdline if cmdline else name
    if not text:
        return "<unknown>"
    if len(text) <= max_length:
        return text
    # Truncate and add ellipsis, ensuring total length is max_length
    return text[: max_length - 3] + "..."


class ProcessWidget(Widget):
    """Widget for displaying process list with DataTable.

    Displays a sortable table of processes with columns for PID, User, CPU%,
    MEM%, VSZ, RSS, State, Runtime, and Command.

    Attributes:
        sort_column: Current sort column
        sort_direction: Current sort direction
        filter_text: Text filter for processes
        tree_view: Whether to show processes in tree view
        command_max_length: Maximum length for command column

    Example:
        ```python
        process_widget = ProcessWidget()
        await process_widget.update_data(process_list_data)
        selected_pid = process_widget.get_selected_pid()
        ```
    """

    class SortChanged(Message):
        """Message sent when sort column or direction changes."""

        def __init__(self, column: ProcessColumn, direction: SortDirection) -> None:
            """Initialize the message.

            Args:
                column: The new sort column
                direction: The new sort direction
            """
            super().__init__()
            self.column = column
            self.direction = direction

    class TreeViewToggled(Message):
        """Message sent when tree view is toggled."""

        def __init__(self, enabled: bool) -> None:
            """Initialize the message.

            Args:
                enabled: Whether tree view is now enabled
            """
            super().__init__()
            self.enabled = enabled

    class FilterChanged(Message):
        """Message sent when filter text changes."""

        def __init__(self, filter_text: str) -> None:
            """Initialize the message.

            Args:
                filter_text: The new filter text
            """
            super().__init__()
            self.filter_text = filter_text

    class ProcessSelected(Message):
        """Message sent when a process row is selected via mouse click."""

        def __init__(self, pid: int, process: ProcessInfo | None) -> None:
            """Initialize the message.

            Args:
                pid: The PID of the selected process
                process: The ProcessInfo of the selected process, or None
            """
            super().__init__()
            self.pid = pid
            self.process = process

    class ProcessDoubleClicked(Message):
        """Message sent when a process row is double-clicked."""

        def __init__(self, pid: int, process: ProcessInfo | None) -> None:
            """Initialize the message.

            Args:
                pid: The PID of the double-clicked process
                process: The ProcessInfo of the double-clicked process, or None
            """
            super().__init__()
            self.pid = pid
            self.process = process

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    ProcessWidget {
        width: 100%;
        height: 100%;
        layout: vertical;
    }

    ProcessWidget DataTable {
        width: 100%;
        height: 1fr;
        scrollbar-size: 1 1;
    }

    ProcessWidget .summary-bar {
        width: 100%;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }

    ProcessWidget DataTable > .datatable--cursor {
        background: $accent;
    }

    ProcessWidget .high-cpu {
        color: $warning;
    }

    ProcessWidget .high-mem {
        color: $error;
    }
    """

    # Reactive properties for sort state
    sort_column: reactive[ProcessColumn] = reactive(ProcessColumn.CPU)
    sort_direction: reactive[SortDirection] = reactive(SortDirection.DESCENDING)
    filter_text: reactive[str] = reactive("")
    tree_view: reactive[bool] = reactive(False)

    # Thresholds for highlighting
    HIGH_CPU_THRESHOLD: ClassVar[float] = 50.0
    HIGH_MEM_THRESHOLD: ClassVar[float] = 25.0

    def __init__(
        self,
        sort_column: ProcessColumn = ProcessColumn.CPU,
        sort_direction: SortDirection = SortDirection.DESCENDING,
        command_max_length: int = 50,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the ProcessWidget.

        Args:
            sort_column: Initial sort column
            sort_direction: Initial sort direction
            command_max_length: Maximum length for command column
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.sort_column = sort_column
        self.sort_direction = sort_direction
        self.command_max_length = command_max_length
        self._data: ProcessListData | None = None
        self._pid_to_row_key: dict[int, RowKey] = {}

    def compose(self) -> ComposeResult:
        """Compose the widget with DataTable and summary bar."""
        yield DataTable(id="process-table", cursor_type="row")
        yield Label("", id="summary-bar", classes="summary-bar")

    def on_mount(self) -> None:
        """Initialize the DataTable when mounted."""
        table = self.query_one("#process-table", DataTable)
        self._setup_columns(table)

        # If data was set before mounting, apply it now
        if self._data is not None:
            self._populate_table()

    def _setup_columns(self, table: DataTable) -> None:
        """Set up the DataTable columns.

        Args:
            table: The DataTable to configure
        """
        for column in ProcessColumn:
            display_name, width, _ = COLUMN_CONFIG[column]
            # Add sort indicator to current sort column
            if column == self.sort_column:
                indicator = "▲" if self.sort_direction == SortDirection.ASCENDING else "▼"
                display_name = display_name + indicator

            if width is not None:
                table.add_column(display_name, key=column.value, width=width)
            else:
                table.add_column(display_name, key=column.value)

    def _get_sort_key(self, proc: ProcessInfo) -> tuple:
        """Get sort key for a process.

        Args:
            proc: Process info to get key for

        Returns:
            Tuple for sorting
        """
        column = self.sort_column

        if column == ProcessColumn.PID:
            return (proc.pid,)
        if column == ProcessColumn.USER:
            return (proc.username.lower(),)
        if column == ProcessColumn.CPU:
            return (proc.cpu_percent,)
        if column == ProcessColumn.MEM:
            return (proc.memory_percent,)
        if column == ProcessColumn.VSZ:
            return (proc.memory_vms_bytes,)
        if column == ProcessColumn.RSS:
            return (proc.memory_rss_bytes,)
        if column == ProcessColumn.STATE:
            return (proc.status,)
        if column == ProcessColumn.RUNTIME:
            return (proc.create_time,)
        if column == ProcessColumn.COMMAND:
            return ((proc.cmdline or proc.name).lower(),)

        return (proc.cpu_percent,)  # Default

    def _format_process_row(self, proc: ProcessInfo) -> tuple:
        """Format a process as a table row.

        Args:
            proc: Process info to format

        Returns:
            Tuple of formatted cell values
        """
        # Format state with style
        state_info = STATE_STYLES.get(proc.status, (proc.status[:1].upper(), ""))
        state_symbol = state_info[0]

        return (
            str(proc.pid).rjust(_PID_COLUMN_WIDTH),
            proc.username[:12] if proc.username else "",
            f"{proc.cpu_percent:>6.1f}",
            f"{proc.memory_percent:>6.1f}",
            f"{format_bytes(proc.memory_vms_bytes):>7}",
            f"{format_bytes(proc.memory_rss_bytes):>7}",
            state_symbol,
            f"{format_runtime(proc.create_time):>10}",
            format_command(proc.cmdline, proc.name),
        )

    def update_data(self, data: ProcessListData) -> None:
        """Update the widget with new process data.

        Args:
            data: ProcessListData from the collector
        """
        self._data = data

        if not self.is_mounted:
            return

        self._populate_table()

    def _populate_table(self) -> None:
        """Populate the DataTable with current data.

        This is called both from update_data (when data arrives after mounting)
        and from on_mount (when data was set before mounting).
        """
        if self._data is None:
            return

        data = self._data
        table = self.query_one("#process-table", DataTable)
        summary = self.query_one("#summary-bar", Label)

        # Filter processes first
        filtered_processes = [p for p in data.processes if self._matches_filter(p)]

        # Save scroll position and cursor before clearing
        saved_scroll_x = table.scroll_x
        saved_scroll_y = table.scroll_y
        saved_cursor_row = table.cursor_row

        # Clear and rebuild table
        table.clear()
        self._pid_to_row_key.clear()

        if self.tree_view:
            # Tree view mode
            tree_data = self._build_process_tree(filtered_processes)
            for proc, indent_level in tree_data:
                row_key = table.add_row(
                    *self._format_process_row_tree(proc, indent_level),
                    key=str(proc.pid),
                )
                self._pid_to_row_key[proc.pid] = row_key
        else:
            # Flat list mode - sort processes
            sorted_processes = sorted(
                filtered_processes,
                key=self._get_sort_key,
                reverse=(self.sort_direction == SortDirection.DESCENDING),
            )
            for proc in sorted_processes:
                row_key = table.add_row(*self._format_process_row(proc), key=str(proc.pid))
                self._pid_to_row_key[proc.pid] = row_key

        # Build summary parts
        summary_parts = [
            f"Total: {data.total_count}",
            f"Running: {data.running_count}",
        ]

        if self.filter_text:
            summary_parts.append(f"Filtered: {len(filtered_processes)}")
            summary_parts.append(f"Filter: '{self.filter_text}'")

        if self.tree_view:
            summary_parts.append("Tree View")
        else:
            sort_dir = "(asc)" if self.sort_direction == SortDirection.ASCENDING else "(desc)"
            summary_parts.append(f"Sort: {COLUMN_CONFIG[self.sort_column][0]} {sort_dir}")

        # Update summary
        summary.update(" | ".join(summary_parts))

        # Restore scroll position and cursor after layout completes
        row_count = table.row_count
        has_position_to_restore = (
            saved_cursor_row is not None or saved_scroll_x > 0 or saved_scroll_y > 0
        )
        if row_count > 0 and has_position_to_restore:
            def restore_scroll() -> None:
                """Restore scroll position after layout."""
                if saved_cursor_row is not None and table.row_count > 0:
                    target_row = min(saved_cursor_row, table.row_count - 1)
                    table.move_cursor(row=target_row)
                if saved_scroll_x > 0:
                    table.scroll_x = saved_scroll_x
                if saved_scroll_y > 0:
                    table.scroll_y = saved_scroll_y

            self.call_after_refresh(restore_scroll)

    def get_selected_pid(self) -> int | None:
        """Get the PID of the currently selected process.

        Returns:
            PID of selected process, or None if no selection
        """
        if not self.is_mounted:
            return None

        table = self.query_one("#process-table", DataTable)

        if table.cursor_row is None or table.row_count == 0:
            return None

        try:
            # get_row_at returns the row data directly, not a key
            row_data = table.get_row_at(table.cursor_row)
            # The first cell is the PID
            if row_data:
                return int(row_data[0])
        except Exception:
            pass

        return None

    def get_selected_process(self) -> ProcessInfo | None:
        """Get the ProcessInfo of the currently selected process.

        Returns:
            ProcessInfo of selected process, or None if no selection
        """
        if self._data is None:
            return None

        pid = self.get_selected_pid()
        if pid is None:
            return None

        for proc in self._data.processes:
            if proc.pid == pid:
                return proc

        return None

    def set_sort(self, column: ProcessColumn, direction: SortDirection | None = None) -> None:
        """Set the sort column and optionally direction.

        If the same column is selected, toggles direction.
        If a new column is selected, uses the provided direction or defaults
        to descending.

        Args:
            column: Column to sort by
            direction: Sort direction, or None to toggle/default
        """
        if column == self.sort_column and direction is None:
            # Toggle direction
            if self.sort_direction == SortDirection.ASCENDING:
                self.sort_direction = SortDirection.DESCENDING
            else:
                self.sort_direction = SortDirection.ASCENDING
        else:
            self.sort_column = column
            self.sort_direction = direction or SortDirection.DESCENDING

        # Re-render with new sort
        if self._data is not None:
            # Update column headers to show sort indicator
            self._refresh_column_headers()
            self.update_data(self._data)

    def _refresh_column_headers(self) -> None:
        """Refresh column headers with current sort indicator."""
        if not self.is_mounted:
            return

        # DataTable doesn't support updating column labels directly,
        # so we need to track this in the data display instead
        # The sort indicator is shown in the summary bar

    def set_filter(self, filter_text: str) -> None:
        """Set the filter text for process filtering.

        Args:
            filter_text: Text to filter processes by (matches command, user, etc.)
        """
        self.filter_text = filter_text
        # Re-apply filter if we have data
        if self._data is not None:
            self.update_data(self._data)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header click for sorting.

        Args:
            event: Header selection event
        """
        # Map column key back to ProcessColumn
        column_key = str(event.column_key)
        try:
            column = ProcessColumn(column_key)
            self.set_sort(column)
        except ValueError:
            pass  # Unknown column key

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection via mouse click.

        When a row is clicked, this posts a ProcessSelected message with the
        PID and ProcessInfo of the selected process.

        Args:
            event: Row selection event from DataTable
        """
        # Get the PID from the selected row
        pid = self.get_selected_pid()
        if pid is not None:
            process = self.get_selected_process()
            self.post_message(self.ProcessSelected(pid, process))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight changes (cursor movement).

        This is triggered when the cursor moves to a different row, either
        via keyboard navigation or mouse click. The visual feedback is handled
        by DataTable's built-in cursor styling.

        Args:
            event: Row highlighted event from DataTable
        """
        # Visual feedback is handled by DataTable's cursor styling
        _ = event  # Acknowledge the event parameter

    def get_process_count(self) -> int:
        """Get the total number of processes.

        Returns:
            Number of processes, or 0 if no data
        """
        if self._data is None:
            return 0
        return self._data.total_count

    def get_running_count(self) -> int:
        """Get the number of running processes.

        Returns:
            Number of running processes, or 0 if no data
        """
        if self._data is None:
            return 0
        return self._data.running_count

    def cycle_sort(self) -> None:
        """Cycle through sort columns in predefined order.

        Cycles through: CPU% -> MEM% -> PID -> User -> Command -> (repeat)
        When cycling to a new column, defaults to descending order.
        """
        try:
            current_index = SORT_CYCLE_ORDER.index(self.sort_column)
            next_index = (current_index + 1) % len(SORT_CYCLE_ORDER)
        except ValueError:
            # Current column not in cycle order, start from beginning
            next_index = 0

        next_column = SORT_CYCLE_ORDER[next_index]
        self.sort_column = next_column
        self.sort_direction = SortDirection.DESCENDING

        # Post message about sort change
        self.post_message(self.SortChanged(next_column, self.sort_direction))

        # Re-render with new sort
        if self._data is not None:
            self._refresh_column_headers()
            self.update_data(self._data)

    def toggle_tree_view(self) -> None:
        """Toggle between flat list and tree view.

        Tree view shows parent-child process relationships with indentation.
        """
        self.tree_view = not self.tree_view

        # Post message about tree view change
        self.post_message(self.TreeViewToggled(self.tree_view))

        # Re-render with new view mode
        if self._data is not None:
            self.update_data(self._data)

    def clear_filter(self) -> None:
        """Clear the current filter text."""
        if self.filter_text:
            self.filter_text = ""
            self.post_message(self.FilterChanged(""))
            if self._data is not None:
                self.update_data(self._data)

    def _matches_filter(self, proc: ProcessInfo) -> bool:
        """Check if a process matches the current filter.

        Args:
            proc: Process info to check

        Returns:
            True if the process matches the filter or filter is empty
        """
        if not self.filter_text:
            return True

        filter_lower = self.filter_text.lower()

        # Check against PID (exact or prefix match)
        if str(proc.pid).startswith(self.filter_text):
            return True

        # Check against name
        if filter_lower in proc.name.lower():
            return True

        # Check against command line
        if proc.cmdline and filter_lower in proc.cmdline.lower():
            return True

        # Check against username
        return filter_lower in proc.username.lower()

    def _build_process_tree(self, processes: list[ProcessInfo]) -> list[tuple[ProcessInfo, int]]:
        """Build a tree structure from flat process list.

        Args:
            processes: Flat list of processes

        Returns:
            List of (process, indent_level) tuples in tree order
        """
        # Build parent-child mapping
        pid_to_proc: dict[int, ProcessInfo] = {p.pid: p for p in processes}
        children: dict[int, list[ProcessInfo]] = {}

        for proc in processes:
            ppid = getattr(proc, "ppid", 0)
            if ppid not in children:
                children[ppid] = []
            children[ppid].append(proc)

        # Sort children by the current sort criteria
        for ppid in children:
            children[ppid] = sorted(
                children[ppid],
                key=self._get_sort_key,
                reverse=(self.sort_direction == SortDirection.DESCENDING),
            )

        result: list[tuple[ProcessInfo, int]] = []

        def add_subtree(pid: int, level: int) -> None:
            """Recursively add process and its children."""
            if pid in pid_to_proc:
                result.append((pid_to_proc[pid], level))
            for child in children.get(pid, []):
                if child.pid != pid:  # Avoid self-reference
                    add_subtree(child.pid, level + 1)

        # Find root processes (those whose parent is not in our list or parent is 0/1)
        root_processes = []
        for proc in processes:
            ppid = getattr(proc, "ppid", 0)
            if ppid not in pid_to_proc or ppid in (0, 1):
                root_processes.append(proc)

        # Sort roots by current sort criteria
        root_processes = sorted(
            root_processes,
            key=self._get_sort_key,
            reverse=(self.sort_direction == SortDirection.DESCENDING),
        )

        # Build tree from each root
        for root in root_processes:
            result.append((root, 0))
            for child in children.get(root.pid, []):
                add_subtree(child.pid, 1)

        return result

    def _format_process_row_tree(self, proc: ProcessInfo, indent_level: int) -> tuple:
        """Format a process as a table row with tree indentation.

        Args:
            proc: Process info to format
            indent_level: Number of levels to indent (for tree view)

        Returns:
            Tuple of formatted cell values
        """
        # Format state with style
        state_info = STATE_STYLES.get(proc.status, (proc.status[:1].upper(), ""))
        state_symbol = state_info[0]

        # Add tree indentation to command
        indent = "  " * indent_level
        tree_prefix = "|- " if indent_level > 0 else ""
        command = format_command(proc.cmdline, proc.name)
        command_display = f"{indent}{tree_prefix}{command}"

        return (
            str(proc.pid).rjust(_PID_COLUMN_WIDTH),
            proc.username[:12] if proc.username else "",
            f"{proc.cpu_percent:>6.1f}",
            f"{proc.memory_percent:>6.1f}",
            f"{format_bytes(proc.memory_vms_bytes):>7}",
            f"{format_bytes(proc.memory_rss_bytes):>7}",
            state_symbol,
            f"{format_runtime(proc.create_time):>10}",
            command_display,
        )
