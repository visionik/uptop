"""Tests for the ProcessWidget.

This module tests the ProcessWidget functionality including:
- Widget instantiation and initialization
- DataTable column setup
- Data update and display
- Sorting functionality
- Selection tracking
- Helper functions for formatting
"""

import time

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Label

from uptop.plugins.processes import ProcessInfo, ProcessListData
from uptop.tui.panes.process_widget import (
    COLUMN_CONFIG,
    ProcessColumn,
    ProcessWidget,
    SortDirection,
    format_bytes,
    format_runtime,
    truncate_command,
)

# ============================================================================
# Helper Function Tests
# ============================================================================


class TestFormatBytes:
    """Tests for format_bytes helper function."""

    def test_format_bytes_zero(self) -> None:
        """Test formatting zero bytes."""
        assert format_bytes(0) == "0"

    def test_format_bytes_small(self) -> None:
        """Test formatting small values (< 1K)."""
        assert format_bytes(500) == "500"
        assert format_bytes(1023) == "1023"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_bytes(1024) == "1.00K"
        assert format_bytes(1536) == "1.50K"
        assert format_bytes(10240) == "10.0K"
        assert format_bytes(102400) == "100K"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_bytes(1024 * 1024) == "1.00M"
        assert format_bytes(1024 * 1024 * 256) == "256M"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_bytes(1024**3) == "1.00G"
        assert format_bytes(1024**3 * 2) == "2.00G"
        assert format_bytes(1024**3 * 16) == "16.0G"

    def test_format_bytes_negative(self) -> None:
        """Test formatting negative values returns zero."""
        assert format_bytes(-100) == "0"


class TestFormatRuntime:
    """Tests for format_runtime helper function."""

    def test_format_runtime_zero(self) -> None:
        """Test formatting zero create_time."""
        assert format_runtime(0) == "00:00:00"

    def test_format_runtime_negative(self) -> None:
        """Test formatting negative create_time."""
        assert format_runtime(-1000) == "00:00:00"

    def test_format_runtime_recent(self) -> None:
        """Test formatting a recently created process."""
        now = time.time()
        recent = now - 65  # 1 minute 5 seconds ago
        result = format_runtime(recent)
        # Should be approximately 00:01:05
        assert result.startswith("00:01:")

    def test_format_runtime_hours(self) -> None:
        """Test formatting a process running for hours."""
        now = time.time()
        hours_ago = now - 3665  # 1 hour, 1 minute, 5 seconds ago
        result = format_runtime(hours_ago)
        assert result.startswith("01:01:")

    def test_format_runtime_many_hours(self) -> None:
        """Test formatting a process running for many hours."""
        now = time.time()
        many_hours = now - (100 * 3600 + 30 * 60 + 15)  # 100:30:15
        result = format_runtime(many_hours)
        assert result == "100:30:15"


class TestTruncateCommand:
    """Tests for truncate_command helper function."""

    def test_truncate_short_command(self) -> None:
        """Test that short commands are not truncated."""
        result = truncate_command("python test.py", "python", max_length=50)
        assert result == "python test.py"

    def test_truncate_long_command(self) -> None:
        """Test that long commands are truncated."""
        long_cmd = "python -m very.long.module.name --with=many --options=here"
        result = truncate_command(long_cmd, "python", max_length=30)
        assert len(result) == 30
        assert result.endswith("...")

    def test_truncate_none_cmdline_uses_name(self) -> None:
        """Test that None cmdline falls back to process name."""
        result = truncate_command(None, "python3", max_length=50)
        assert result == "python3"

    def test_truncate_empty_returns_unknown(self) -> None:
        """Test that empty command returns <unknown>."""
        result = truncate_command(None, "", max_length=50)
        assert result == "<unknown>"

    def test_truncate_exact_length(self) -> None:
        """Test command exactly at max_length."""
        cmd = "a" * 50
        result = truncate_command(cmd, "test", max_length=50)
        assert result == cmd
        assert len(result) == 50


# ============================================================================
# ProcessColumn and SortDirection Tests
# ============================================================================


class TestProcessColumn:
    """Tests for ProcessColumn enum."""

    def test_all_columns_defined(self) -> None:
        """Test that all expected columns are defined."""
        expected = {"pid", "user", "cpu", "mem", "vsz", "rss", "state", "runtime", "command"}
        actual = {col.value for col in ProcessColumn}
        assert actual == expected

    def test_column_config_matches(self) -> None:
        """Test that COLUMN_CONFIG has entry for each column."""
        for col in ProcessColumn:
            assert col in COLUMN_CONFIG


class TestSortDirection:
    """Tests for SortDirection enum."""

    def test_sort_direction_values(self) -> None:
        """Test SortDirection has expected values."""
        assert SortDirection.ASCENDING.value == "asc"
        assert SortDirection.DESCENDING.value == "desc"


# ============================================================================
# ProcessWidget Unit Tests
# ============================================================================


class TestProcessWidgetUnit:
    """Unit tests for ProcessWidget without Textual app context."""

    def test_initialization_defaults(self) -> None:
        """Test ProcessWidget initializes with correct defaults."""
        widget = ProcessWidget()
        assert widget.sort_column == ProcessColumn.CPU
        assert widget.sort_direction == SortDirection.DESCENDING
        assert widget.filter_text == ""
        assert widget.command_max_length == 50
        assert widget._data is None

    def test_initialization_custom_values(self) -> None:
        """Test ProcessWidget initializes with custom values."""
        widget = ProcessWidget(
            sort_column=ProcessColumn.MEM,
            sort_direction=SortDirection.ASCENDING,
            command_max_length=100,
            id="my-process-widget",
        )
        assert widget.sort_column == ProcessColumn.MEM
        assert widget.sort_direction == SortDirection.ASCENDING
        assert widget.command_max_length == 100
        assert widget.id == "my-process-widget"

    def test_get_process_count_no_data(self) -> None:
        """Test get_process_count returns 0 when no data."""
        widget = ProcessWidget()
        assert widget.get_process_count() == 0

    def test_get_running_count_no_data(self) -> None:
        """Test get_running_count returns 0 when no data."""
        widget = ProcessWidget()
        assert widget.get_running_count() == 0

    def test_has_default_css(self) -> None:
        """Test ProcessWidget has default CSS defined."""
        assert ProcessWidget.DEFAULT_CSS is not None
        assert "ProcessWidget" in ProcessWidget.DEFAULT_CSS
        assert "DataTable" in ProcessWidget.DEFAULT_CSS

    def test_set_filter(self) -> None:
        """Test set_filter updates filter_text."""
        widget = ProcessWidget()
        widget.set_filter("python")
        assert widget.filter_text == "python"


# ============================================================================
# Test Fixtures
# ============================================================================


def create_sample_process(
    pid: int = 1234,
    name: str = "python",
    username: str = "testuser",
    cpu_percent: float = 25.5,
    memory_percent: float = 10.0,
    status: str = "running",
    create_time: float | None = None,
    cmdline: str | None = "python test.py",
) -> ProcessInfo:
    """Create a sample ProcessInfo for testing.

    Args:
        pid: Process ID
        name: Process name
        username: Process owner
        cpu_percent: CPU usage percentage
        memory_percent: Memory usage percentage
        status: Process status
        create_time: Creation timestamp (defaults to 1 hour ago)
        cmdline: Command line

    Returns:
        ProcessInfo instance
    """
    if create_time is None:
        create_time = time.time() - 3600  # 1 hour ago

    return ProcessInfo(
        pid=pid,
        name=name,
        username=username,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        memory_rss_bytes=1024 * 1024 * 100,
        memory_vms_bytes=1024 * 1024 * 200,
        status=status,
        create_time=create_time,
        cmdline=cmdline,
        num_threads=4,
        source="test",
    )


def create_sample_process_list(count: int = 5) -> ProcessListData:
    """Create a sample ProcessListData for testing.

    Args:
        count: Number of processes to create

    Returns:
        ProcessListData instance
    """
    processes = []
    running_count = 0

    for i in range(count):
        status = "running" if i % 3 == 0 else "sleeping"
        if status == "running":
            running_count += 1

        proc = create_sample_process(
            pid=1000 + i,
            name=f"process_{i}",
            username=f"user{i % 2}",
            cpu_percent=float(i * 10),
            memory_percent=float(i * 5),
            status=status,
            cmdline=f"/usr/bin/process_{i} --arg{i}",
        )
        processes.append(proc)

    return ProcessListData(
        processes=processes,
        total_count=count,
        running_count=running_count,
        source="test",
    )


# ============================================================================
# ProcessWidget Textual App Tests
# ============================================================================


class ProcessWidgetTestApp(App[None]):
    """Test app for ProcessWidget testing."""

    def __init__(
        self,
        sort_column: ProcessColumn = ProcessColumn.CPU,
        sort_direction: SortDirection = SortDirection.DESCENDING,
        command_max_length: int = 50,
        initial_data: ProcessListData | None = None,
    ) -> None:
        """Initialize test app with configurable widget.

        Args:
            sort_column: Initial sort column
            sort_direction: Initial sort direction
            command_max_length: Max command length
            initial_data: Initial data to load
        """
        super().__init__()
        self._sort_column = sort_column
        self._sort_direction = sort_direction
        self._command_max_length = command_max_length
        self._initial_data = initial_data

    def compose(self) -> ComposeResult:
        """Compose the test app with a ProcessWidget."""
        yield ProcessWidget(
            sort_column=self._sort_column,
            sort_direction=self._sort_direction,
            command_max_length=self._command_max_length,
            id="test-process-widget",
        )

    def on_mount(self) -> None:
        """Load initial data if provided."""
        if self._initial_data is not None:
            widget = self.query_one("#test-process-widget", ProcessWidget)
            widget.update_data(self._initial_data)


class TestProcessWidgetRendering:
    """Integration tests for ProcessWidget rendering using Textual pilot."""

    @pytest.mark.asyncio
    async def test_widget_composes_correctly(self) -> None:
        """Test that ProcessWidget composes with DataTable and summary."""
        app = ProcessWidgetTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            # Should have a DataTable
            table = widget.query_one("#process-table", DataTable)
            assert table is not None

            # Should have summary bar
            summary = widget.query_one("#summary-bar")
            assert summary is not None

    @pytest.mark.asyncio
    async def test_columns_are_setup(self) -> None:
        """Test that DataTable has all expected columns."""
        app = ProcessWidgetTestApp()
        async with app.run_test() as pilot:
            # Wait for mount to complete
            await pilot.pause()
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            table = widget.query_one("#process-table", DataTable)

            # Should have 9 columns
            assert len(table.ordered_columns) == 9

    @pytest.mark.asyncio
    async def test_update_data_populates_table(self) -> None:
        """Test that update_data populates the DataTable."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            table = widget.query_one("#process-table", DataTable)

            # Should have 3 rows
            assert table.row_count == 3

    @pytest.mark.asyncio
    async def test_get_process_count_with_data(self) -> None:
        """Test get_process_count returns correct count."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            assert widget.get_process_count() == 5

    @pytest.mark.asyncio
    async def test_get_running_count_with_data(self) -> None:
        """Test get_running_count returns correct count."""
        data = create_sample_process_list(6)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            # With our creation function, every 3rd process is running
            # indices 0, 3 = 2 running out of 6
            assert widget.get_running_count() == 2

    @pytest.mark.asyncio
    async def test_sorting_by_cpu(self) -> None:
        """Test that data is sorted by CPU by default."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.CPU,
            sort_direction=SortDirection.DESCENDING,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            table = widget.query_one("#process-table", DataTable)

            # First row should be highest CPU (index 2 has cpu_percent=20.0)
            if table.row_count > 0:
                first_row = table.get_row_at(0)
                # The CPU column is index 2 (after PID and User)
                assert float(first_row[2]) == 20.0

    @pytest.mark.asyncio
    async def test_set_sort_changes_order(self) -> None:
        """Test that set_sort changes the sort order."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            # Change to sort by PID ascending
            widget.set_sort(ProcessColumn.PID, SortDirection.ASCENDING)
            await pilot.pause()

            table = widget.query_one("#process-table", DataTable)
            if table.row_count > 0:
                first_row = table.get_row_at(0)
                # First row should be lowest PID (1000)
                assert first_row[0] == "1000"

    @pytest.mark.asyncio
    async def test_set_sort_toggle_direction(self) -> None:
        """Test that set_sort toggles direction on same column."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.CPU,
            sort_direction=SortDirection.DESCENDING,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            # Toggle CPU sort (should go from DESC to ASC)
            widget.set_sort(ProcessColumn.CPU)
            await pilot.pause()

            assert widget.sort_direction == SortDirection.ASCENDING

    @pytest.mark.asyncio
    async def test_summary_bar_updates(self) -> None:
        """Test that summary bar shows correct information."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            # Wait for mount and data update
            await pilot.pause()
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            summary = widget.query_one("#summary-bar", Label)

            # Summary should contain count information
            summary_text = summary.content
            assert "Total: 5" in summary_text
            assert "Running:" in summary_text


class TestProcessWidgetSelection:
    """Tests for process selection functionality."""

    @pytest.mark.asyncio
    async def test_get_selected_pid_no_data(self) -> None:
        """Test get_selected_pid returns None when no data."""
        app = ProcessWidgetTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            assert widget.get_selected_pid() is None

    @pytest.mark.asyncio
    async def test_get_selected_pid_with_data(self) -> None:
        """Test get_selected_pid returns PID of selected row."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            table = widget.query_one("#process-table", DataTable)

            # Select first row
            table.cursor_coordinate = (0, 0)
            await pilot.pause()

            # Should return the PID of the first row
            pid = widget.get_selected_pid()
            assert pid is not None
            assert pid in [1000, 1001, 1002]  # One of the sample PIDs

    @pytest.mark.asyncio
    async def test_get_selected_process_no_data(self) -> None:
        """Test get_selected_process returns None when no data."""
        app = ProcessWidgetTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            assert widget.get_selected_process() is None

    @pytest.mark.asyncio
    async def test_get_selected_process_with_data(self) -> None:
        """Test get_selected_process returns ProcessInfo of selected row."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            table = widget.query_one("#process-table", DataTable)

            # Select first row
            table.cursor_coordinate = (0, 0)
            await pilot.pause()

            process = widget.get_selected_process()
            assert process is not None
            assert isinstance(process, ProcessInfo)


class TestProcessWidgetColumnConfig:
    """Tests for COLUMN_CONFIG configuration."""

    def test_all_columns_have_config(self) -> None:
        """Test that all ProcessColumn values have config entries."""
        for col in ProcessColumn:
            assert col in COLUMN_CONFIG
            config = COLUMN_CONFIG[col]
            assert len(config) == 3  # (display_name, width, is_sortable)

    def test_column_config_types(self) -> None:
        """Test that config values have correct types."""
        for _col, config in COLUMN_CONFIG.items():
            display_name, width, is_sortable = config
            assert isinstance(display_name, str)
            assert width is None or isinstance(width, int)
            assert isinstance(is_sortable, bool)

    def test_command_column_has_flexible_width(self) -> None:
        """Test that command column has flexible width (None)."""
        _, width, _ = COLUMN_CONFIG[ProcessColumn.COMMAND]
        assert width is None
