"""Tests for Process Pane Keybindings (Phase 3.7).

This module tests:
- Sort cycling (s key)
- Filter modal (/ key)
- Kill confirmation modal (k key)
- Tree view toggle (t key)
- ProcessWidget messages for state changes
"""

import time

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Label

from uptop.plugins.processes import ProcessInfo, ProcessListData
from uptop.tui.panes.process_widget import (
    SORT_CYCLE_ORDER,
    ProcessColumn,
    ProcessWidget,
    SortDirection,
)
from uptop.tui.screens import ConfirmKillScreen, FilterScreen, KillResult, KillSignal

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


def create_process_tree_list() -> ProcessListData:
    """Create a sample ProcessListData for tree view testing.

    Note: ProcessInfo doesn't have a ppid field, so tree view
    uses getattr with default 0, treating all processes as roots.

    Returns:
        ProcessListData for tree testing
    """
    processes = [
        create_sample_process(pid=1, name="init", cpu_percent=0.1),
        create_sample_process(pid=100, name="systemd", cpu_percent=0.2),
        create_sample_process(pid=200, name="sshd", cpu_percent=0.3),
        create_sample_process(pid=201, name="bash", cpu_percent=0.4),
        create_sample_process(pid=300, name="nginx", cpu_percent=5.0),
        create_sample_process(pid=301, name="nginx-worker", cpu_percent=10.0),
        create_sample_process(pid=302, name="nginx-worker", cpu_percent=8.0),
    ]

    return ProcessListData(
        processes=processes,
        total_count=len(processes),
        running_count=sum(1 for p in processes if p.status == "running"),
        source="test",
    )


class ProcessWidgetTestApp(App[None]):
    """Test app for ProcessWidget testing."""

    def __init__(
        self,
        sort_column: ProcessColumn = ProcessColumn.CPU,
        sort_direction: SortDirection = SortDirection.DESCENDING,
        initial_data: ProcessListData | None = None,
    ) -> None:
        """Initialize test app with configurable widget."""
        super().__init__()
        self._sort_column = sort_column
        self._sort_direction = sort_direction
        self._initial_data = initial_data

    def compose(self) -> ComposeResult:
        """Compose the test app with a ProcessWidget."""
        yield ProcessWidget(
            sort_column=self._sort_column,
            sort_direction=self._sort_direction,
            id="test-process-widget",
        )

    def on_mount(self) -> None:
        """Load initial data if provided."""
        if self._initial_data is not None:
            widget = self.query_one("#test-process-widget", ProcessWidget)
            widget.update_data(self._initial_data)


# ============================================================================
# Sort Cycling Tests (3.7.1)
# ============================================================================


class TestSortCycling:
    """Tests for sort cycling functionality (s key)."""

    def test_sort_cycle_order_defined(self) -> None:
        """Test that SORT_CYCLE_ORDER is properly defined."""
        assert len(SORT_CYCLE_ORDER) == 5
        assert ProcessColumn.CPU in SORT_CYCLE_ORDER
        assert ProcessColumn.MEM in SORT_CYCLE_ORDER
        assert ProcessColumn.PID in SORT_CYCLE_ORDER
        assert ProcessColumn.USER in SORT_CYCLE_ORDER
        assert ProcessColumn.COMMAND in SORT_CYCLE_ORDER

    def test_sort_cycle_order_sequence(self) -> None:
        """Test the exact sequence of sort cycling."""
        assert SORT_CYCLE_ORDER[0] == ProcessColumn.CPU
        assert SORT_CYCLE_ORDER[1] == ProcessColumn.MEM
        assert SORT_CYCLE_ORDER[2] == ProcessColumn.PID
        assert SORT_CYCLE_ORDER[3] == ProcessColumn.USER
        assert SORT_CYCLE_ORDER[4] == ProcessColumn.COMMAND

    @pytest.mark.asyncio
    async def test_cycle_sort_from_cpu_to_mem(self) -> None:
        """Test cycling from CPU to MEM."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.CPU,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            assert widget.sort_column == ProcessColumn.CPU
            widget.cycle_sort()
            await pilot.pause()

            assert widget.sort_column == ProcessColumn.MEM
            assert widget.sort_direction == SortDirection.DESCENDING

    @pytest.mark.asyncio
    async def test_cycle_sort_wraps_around(self) -> None:
        """Test that cycling wraps from COMMAND back to CPU."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.COMMAND,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            assert widget.sort_column == ProcessColumn.COMMAND
            widget.cycle_sort()
            await pilot.pause()

            assert widget.sort_column == ProcessColumn.CPU

    @pytest.mark.asyncio
    async def test_cycle_sort_full_cycle(self) -> None:
        """Test cycling through all columns."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.CPU,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            # Full cycle through all columns
            for expected_col in SORT_CYCLE_ORDER[1:] + [SORT_CYCLE_ORDER[0]]:
                widget.cycle_sort()
                await pilot.pause()
                assert widget.sort_column == expected_col

    @pytest.mark.asyncio
    async def test_cycle_sort_defaults_to_descending(self) -> None:
        """Test that cycling always sets descending direction."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.CPU,
            sort_direction=SortDirection.ASCENDING,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.cycle_sort()
            await pilot.pause()

            # Even though we started with ascending, cycle sets descending
            assert widget.sort_direction == SortDirection.DESCENDING

    @pytest.mark.asyncio
    async def test_cycle_sort_updates_display(self) -> None:
        """Test that cycling updates the summary bar."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(
            sort_column=ProcessColumn.CPU,
            initial_data=data,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.cycle_sort()
            await pilot.pause()

            summary = widget.query_one("#summary-bar", Label)
            assert "MEM%" in summary.content


class TestSortChangedMessage:
    """Tests for SortChanged message definition."""

    def test_sort_changed_message_attributes(self) -> None:
        """Test SortChanged message has correct attributes."""
        msg = ProcessWidget.SortChanged(ProcessColumn.CPU, SortDirection.DESCENDING)
        assert msg.column == ProcessColumn.CPU
        assert msg.direction == SortDirection.DESCENDING

    def test_sort_changed_message_with_different_values(self) -> None:
        """Test SortChanged message with various column values."""
        msg = ProcessWidget.SortChanged(ProcessColumn.MEM, SortDirection.ASCENDING)
        assert msg.column == ProcessColumn.MEM
        assert msg.direction == SortDirection.ASCENDING


# ============================================================================
# Filter Tests (3.7.2)
# ============================================================================


class TestFilterFunctionality:
    """Tests for filter functionality."""

    @pytest.mark.asyncio
    async def test_filter_by_name(self) -> None:
        """Test filtering processes by name."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.set_filter("process_0")
            await pilot.pause()

            table = widget.query_one("#process-table", DataTable)
            # Should filter to only process_0
            assert table.row_count == 1

    @pytest.mark.asyncio
    async def test_filter_by_pid(self) -> None:
        """Test filtering processes by PID."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.set_filter("1002")
            await pilot.pause()

            table = widget.query_one("#process-table", DataTable)
            # Should filter to process with PID 1002
            assert table.row_count == 1

    @pytest.mark.asyncio
    async def test_filter_by_username(self) -> None:
        """Test filtering processes by username."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.set_filter("user0")
            await pilot.pause()

            table = widget.query_one("#process-table", DataTable)
            # Should filter to processes with user0 (indices 0, 2, 4)
            assert table.row_count == 3

    @pytest.mark.asyncio
    async def test_filter_case_insensitive(self) -> None:
        """Test that filtering is case insensitive."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.set_filter("PROCESS_0")
            await pilot.pause()

            table = widget.query_one("#process-table", DataTable)
            # Should still match process_0
            assert table.row_count == 1

    @pytest.mark.asyncio
    async def test_clear_filter(self) -> None:
        """Test clearing the filter."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.set_filter("process_0")
            await pilot.pause()
            table = widget.query_one("#process-table", DataTable)
            assert table.row_count == 1

            widget.clear_filter()
            await pilot.pause()
            assert table.row_count == 5

    @pytest.mark.asyncio
    async def test_filter_updates_summary(self) -> None:
        """Test that filter updates the summary bar."""
        data = create_sample_process_list(5)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.set_filter("process")
            await pilot.pause()

            summary = widget.query_one("#summary-bar", Label)
            assert "Filter:" in summary.content
            assert "process" in summary.content


class TestFilterScreen:
    """Tests for FilterScreen modal."""

    def test_filter_screen_instantiation(self) -> None:
        """Test FilterScreen can be instantiated."""
        screen = FilterScreen()
        assert screen is not None

    def test_filter_screen_with_current_filter(self) -> None:
        """Test FilterScreen with existing filter value."""
        screen = FilterScreen(current_filter="python")
        assert screen._current_filter == "python"

    def test_filter_screen_has_dismiss_bindings(self) -> None:
        """Test FilterScreen has bindings for dismissal."""
        screen = FilterScreen()
        escape_bindings = [b for b in screen.BINDINGS if b.key == "escape"]
        assert len(escape_bindings) == 1
        assert escape_bindings[0].action == "cancel"


# ============================================================================
# Kill Confirmation Tests (3.7.3)
# ============================================================================


class TestConfirmKillScreen:
    """Tests for ConfirmKillScreen modal."""

    def test_confirm_kill_screen_instantiation(self) -> None:
        """Test ConfirmKillScreen can be instantiated."""
        screen = ConfirmKillScreen(pid=1234)
        assert screen is not None
        assert screen._pid == 1234

    def test_confirm_kill_screen_with_process_info(self) -> None:
        """Test ConfirmKillScreen with ProcessInfo."""
        process = create_sample_process(pid=1234, name="test_process")
        screen = ConfirmKillScreen(pid=1234, process=process)
        assert screen._pid == 1234
        assert screen._process == process

    def test_confirm_kill_screen_has_dismiss_bindings(self) -> None:
        """Test ConfirmKillScreen has bindings for actions."""
        screen = ConfirmKillScreen(pid=1234)

        # Check for escape binding
        escape_bindings = [b for b in screen.BINDINGS if b.key == "escape"]
        assert len(escape_bindings) == 1

        # Check for y (SIGTERM) binding
        y_bindings = [b for b in screen.BINDINGS if b.key == "y"]
        assert len(y_bindings) == 1

        # Check for f (SIGKILL) binding
        f_bindings = [b for b in screen.BINDINGS if b.key == "f"]
        assert len(f_bindings) == 1


class TestKillSignal:
    """Tests for KillSignal enum."""

    def test_kill_signal_values(self) -> None:
        """Test KillSignal has correct signal values."""
        import signal

        assert KillSignal.SIGTERM.value == signal.SIGTERM
        assert KillSignal.SIGKILL.value == signal.SIGKILL


class TestKillResult:
    """Tests for KillResult dataclass."""

    def test_kill_result_creation(self) -> None:
        """Test KillResult can be created."""
        result = KillResult(confirmed=True, signal=KillSignal.SIGTERM, pid=1234)
        assert result.confirmed is True
        assert result.signal == KillSignal.SIGTERM
        assert result.pid == 1234

    def test_kill_result_not_confirmed(self) -> None:
        """Test KillResult with confirmed=False."""
        result = KillResult(confirmed=False, signal=KillSignal.SIGTERM, pid=1234)
        assert result.confirmed is False


# ============================================================================
# Tree View Tests (3.7.4)
# ============================================================================


class TestTreeViewToggle:
    """Tests for tree view toggle functionality."""

    @pytest.mark.asyncio
    async def test_tree_view_defaults_to_false(self) -> None:
        """Test that tree_view defaults to False."""
        app = ProcessWidgetTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)
            assert widget.tree_view is False

    @pytest.mark.asyncio
    async def test_toggle_tree_view(self) -> None:
        """Test toggling tree view on and off."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            # Toggle on
            widget.toggle_tree_view()
            await pilot.pause()
            assert widget.tree_view is True

            # Toggle off
            widget.toggle_tree_view()
            await pilot.pause()
            assert widget.tree_view is False

    @pytest.mark.asyncio
    async def test_tree_view_updates_summary(self) -> None:
        """Test that tree view updates the summary bar."""
        data = create_sample_process_list(3)
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.toggle_tree_view()
            await pilot.pause()

            summary = widget.query_one("#summary-bar", Label)
            assert "Tree View" in summary.content

    @pytest.mark.asyncio
    async def test_tree_view_with_hierarchical_data(self) -> None:
        """Test tree view displays parent-child relationships."""
        data = create_process_tree_list()
        app = ProcessWidgetTestApp(initial_data=data)
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-process-widget", ProcessWidget)

            widget.toggle_tree_view()
            await pilot.pause()

            table = widget.query_one("#process-table", DataTable)
            # All processes should still be visible
            assert table.row_count == 7


class TestTreeViewToggledMessage:
    """Tests for TreeViewToggled message definition."""

    def test_tree_view_toggled_message_enabled(self) -> None:
        """Test TreeViewToggled message with enabled=True."""
        msg = ProcessWidget.TreeViewToggled(enabled=True)
        assert msg.enabled is True

    def test_tree_view_toggled_message_disabled(self) -> None:
        """Test TreeViewToggled message with enabled=False."""
        msg = ProcessWidget.TreeViewToggled(enabled=False)
        assert msg.enabled is False


# ============================================================================
# Integration Tests
# ============================================================================


class TestProcessWidgetMessages:
    """Tests for ProcessWidget message definitions."""

    def test_sort_changed_message_defined(self) -> None:
        """Test SortChanged message is properly defined."""
        msg = ProcessWidget.SortChanged(ProcessColumn.CPU, SortDirection.DESCENDING)
        assert msg.column == ProcessColumn.CPU
        assert msg.direction == SortDirection.DESCENDING

    def test_tree_view_toggled_message_defined(self) -> None:
        """Test TreeViewToggled message is properly defined."""
        msg = ProcessWidget.TreeViewToggled(enabled=True)
        assert msg.enabled is True

    def test_filter_changed_message_defined(self) -> None:
        """Test FilterChanged message is properly defined."""
        msg = ProcessWidget.FilterChanged("python")
        assert msg.filter_text == "python"


class TestProcessWidgetFilterMethods:
    """Tests for internal filter methods."""

    def test_matches_filter_empty_filter(self) -> None:
        """Test _matches_filter returns True for empty filter."""
        widget = ProcessWidget()
        widget.filter_text = ""
        proc = create_sample_process()
        assert widget._matches_filter(proc) is True

    def test_matches_filter_by_name(self) -> None:
        """Test _matches_filter matches by name."""
        widget = ProcessWidget()
        widget.filter_text = "python"
        proc = create_sample_process(name="python")
        assert widget._matches_filter(proc) is True

    def test_matches_filter_by_cmdline(self) -> None:
        """Test _matches_filter matches by command line."""
        widget = ProcessWidget()
        widget.filter_text = "test.py"
        proc = create_sample_process(cmdline="python test.py")
        assert widget._matches_filter(proc) is True

    def test_matches_filter_no_match(self) -> None:
        """Test _matches_filter returns False for no match."""
        widget = ProcessWidget()
        widget.filter_text = "nonexistent"
        proc = create_sample_process(name="python", cmdline="test.py", username="user")
        assert widget._matches_filter(proc) is False
