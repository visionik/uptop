"""Tests for Process Pane Plugin."""

from collections import namedtuple
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import psutil
from pydantic import ValidationError
import pytest

from uptop.models import MetricData, MetricType, PluginType, get_metric_type
from uptop.plugins.processes import (
    ProcessCollector,
    ProcessInfo,
    ProcessListData,
    ProcessPane,
)

# ============================================================================
# ProcessInfo Model Tests
# ============================================================================


class TestProcessInfo:
    """Tests for ProcessInfo model validation."""

    def test_valid_process_info(self) -> None:
        """Test creating a valid ProcessInfo."""
        info = ProcessInfo(
            pid=1234,
            name="python",
            username="testuser",
            cpu_percent=25.5,
            memory_percent=10.0,
            memory_rss_bytes=1024 * 1024 * 100,
            memory_vms_bytes=1024 * 1024 * 200,
            status="running",
            create_time=1704067200.0,
            cmdline="python test.py",
            num_threads=4,
            source="test",
        )
        assert info.pid == 1234
        assert info.name == "python"
        assert info.username == "testuser"
        assert info.cpu_percent == 25.5
        assert info.memory_percent == 10.0
        assert info.memory_rss_bytes == 1024 * 1024 * 100
        assert info.memory_vms_bytes == 1024 * 1024 * 200
        assert info.status == "running"
        assert info.create_time == 1704067200.0
        assert info.cmdline == "python test.py"
        assert info.num_threads == 4

    def test_minimal_process_info(self) -> None:
        """Test creating ProcessInfo with only required fields."""
        info = ProcessInfo(pid=1, name="init", source="test")
        assert info.pid == 1
        assert info.name == "init"
        assert info.username == ""
        assert info.cpu_percent == 0.0
        assert info.memory_percent == 0.0
        assert info.memory_rss_bytes == 0
        assert info.memory_vms_bytes == 0
        assert info.status == "unknown"
        assert info.create_time == 0.0
        assert info.cmdline is None
        assert info.num_threads == 1

    def test_invalid_negative_pid(self) -> None:
        """Test that negative PID raises validation error."""
        with pytest.raises(ValidationError):
            ProcessInfo(pid=-1, name="test", source="test")

    def test_invalid_memory_percent_over_100(self) -> None:
        """Test that memory_percent over 100 raises validation error."""
        with pytest.raises(ValidationError):
            ProcessInfo(pid=1, name="test", memory_percent=101.0, source="test")

    def test_invalid_negative_memory(self) -> None:
        """Test that negative memory values raise validation error."""
        with pytest.raises(ValidationError):
            ProcessInfo(pid=1, name="test", memory_rss_bytes=-100, source="test")

    def test_process_info_is_frozen(self) -> None:
        """Test that ProcessInfo is immutable."""
        info = ProcessInfo(pid=1, name="test", source="test")
        with pytest.raises(ValidationError):
            info.pid = 2  # type: ignore

    def test_cmdline_can_be_none(self) -> None:
        """Test that cmdline can be None."""
        info = ProcessInfo(pid=1, name="test", cmdline=None, source="test")
        assert info.cmdline is None


# ============================================================================
# ProcessListData Model Tests
# ============================================================================


class TestProcessListData:
    """Tests for ProcessListData model validation."""

    def test_empty_process_list(self) -> None:
        """Test creating an empty process list."""
        data = ProcessListData(source="test")
        assert data.processes == []
        assert data.total_count == 0
        assert data.running_count == 0

    def test_process_list_with_processes(self) -> None:
        """Test creating a process list with processes."""
        proc1 = ProcessInfo(pid=1, name="init", status="running", source="test")
        proc2 = ProcessInfo(pid=2, name="systemd", status="sleeping", source="test")

        data = ProcessListData(
            processes=[proc1, proc2],
            total_count=2,
            running_count=1,
            source="test",
        )

        assert len(data.processes) == 2
        assert data.total_count == 2
        assert data.running_count == 1
        assert data.processes[0].name == "init"

    def test_invalid_negative_counts(self) -> None:
        """Test that negative counts raise validation error."""
        with pytest.raises(ValidationError):
            ProcessListData(total_count=-1, source="test")

        with pytest.raises(ValidationError):
            ProcessListData(running_count=-1, source="test")

    def test_inherits_from_metric_data(self) -> None:
        """Test that ProcessListData inherits from MetricData."""
        data = ProcessListData(source="test")
        assert isinstance(data, MetricData)
        assert hasattr(data, "timestamp")
        assert hasattr(data, "source")

    def test_timestamp_is_set(self) -> None:
        """Test that timestamp is automatically set."""
        before = datetime.now(UTC)
        data = ProcessListData(source="test")
        after = datetime.now(UTC)

        assert data.timestamp >= before
        assert data.timestamp <= after


# ============================================================================
# Metric Type Tests
# ============================================================================


class TestProcessMetricTypes:
    """Tests for metric type annotations on Process models."""

    def test_process_info_metric_types(self) -> None:
        """Test that ProcessInfo fields have correct metric types."""
        assert get_metric_type(ProcessInfo, "cpu_percent") == MetricType.GAUGE
        assert get_metric_type(ProcessInfo, "memory_percent") == MetricType.GAUGE
        assert get_metric_type(ProcessInfo, "memory_rss_bytes") == MetricType.GAUGE
        assert get_metric_type(ProcessInfo, "memory_vms_bytes") == MetricType.GAUGE
        assert get_metric_type(ProcessInfo, "num_threads") == MetricType.GAUGE
        # Non-metric fields
        assert get_metric_type(ProcessInfo, "pid") is None
        assert get_metric_type(ProcessInfo, "name") is None

    def test_process_list_data_metric_types(self) -> None:
        """Test that ProcessListData fields have correct metric types."""
        assert get_metric_type(ProcessListData, "total_count") == MetricType.GAUGE
        assert get_metric_type(ProcessListData, "running_count") == MetricType.GAUGE


# ============================================================================
# ProcessCollector Tests
# ============================================================================


class TestProcessCollector:
    """Tests for ProcessCollector."""

    def test_collector_attributes(self) -> None:
        """Test collector class attributes."""
        collector = ProcessCollector()
        assert collector.name == "process_collector"
        assert collector.default_interval == 2.0
        assert collector.timeout == 10.0

    def test_get_schema(self) -> None:
        """Test get_schema returns ProcessListData."""
        collector = ProcessCollector()
        assert collector.get_schema() == ProcessListData

    @pytest.mark.asyncio
    async def test_collect_returns_process_list_data(self) -> None:
        """Test that collect returns ProcessListData."""
        collector = ProcessCollector()
        result = await collector.collect()

        assert isinstance(result, ProcessListData)
        assert result.total_count >= 0
        assert result.running_count >= 0
        assert len(result.processes) == result.total_count

    @pytest.mark.asyncio
    async def test_collect_with_mocked_psutil(self) -> None:
        """Test collect with mocked psutil data."""
        # Create mock process info
        MockMemInfo = namedtuple("MockMemInfo", ["rss", "vms"])
        mock_proc_info = {
            "pid": 1234,
            "name": "test_process",
            "username": "testuser",
            "cpu_percent": 5.0,
            "memory_percent": 2.5,
            "memory_info": MockMemInfo(rss=1024 * 1024, vms=2048 * 1024),
            "status": "running",
            "create_time": 1704067200.0,
            "cmdline": ["python", "test.py"],
            "num_threads": 2,
        }

        mock_proc = MagicMock()
        mock_proc.info = mock_proc_info

        with patch("psutil.process_iter") as mock_iter:
            mock_iter.return_value = [mock_proc]

            collector = ProcessCollector()
            result = await collector.collect()

        assert result.total_count == 1
        assert result.running_count == 1
        assert len(result.processes) == 1

        proc = result.processes[0]
        assert proc.pid == 1234
        assert proc.name == "test_process"
        assert proc.username == "testuser"
        assert proc.cpu_percent == 5.0
        assert proc.memory_percent == 2.5
        assert proc.memory_rss_bytes == 1024 * 1024
        assert proc.memory_vms_bytes == 2048 * 1024
        assert proc.status == "running"
        assert proc.cmdline == "python test.py"
        assert proc.num_threads == 2

    @pytest.mark.asyncio
    async def test_collect_handles_access_denied(self) -> None:
        """Test that AccessDenied exceptions are handled gracefully."""
        mock_proc = MagicMock()
        mock_proc.info.__getitem__ = MagicMock(side_effect=psutil.AccessDenied(1234))

        # Create a generator that yields the mock proc but raises on info access
        def mock_iter(*args: Any, **kwargs: Any) -> list[MagicMock]:
            proc = MagicMock()
            type(proc).info = property(
                lambda self: (_ for _ in ()).throw(psutil.AccessDenied(1234))
            )
            return [proc]

        with patch("psutil.process_iter", mock_iter):
            collector = ProcessCollector()
            result = await collector.collect()

        # Should return empty list without raising
        assert result.total_count == 0
        assert len(result.processes) == 0

    @pytest.mark.asyncio
    async def test_collect_handles_no_such_process(self) -> None:
        """Test that NoSuchProcess exceptions are handled gracefully."""

        def mock_iter(*args: Any, **kwargs: Any) -> list[MagicMock]:
            proc = MagicMock()
            type(proc).info = property(
                lambda self: (_ for _ in ()).throw(psutil.NoSuchProcess(1234))
            )
            return [proc]

        with patch("psutil.process_iter", mock_iter):
            collector = ProcessCollector()
            result = await collector.collect()

        # Should return empty list without raising
        assert result.total_count == 0
        assert len(result.processes) == 0

    @pytest.mark.asyncio
    async def test_collect_handles_zombie_process(self) -> None:
        """Test that ZombieProcess exceptions are handled gracefully."""

        def mock_iter(*args: Any, **kwargs: Any) -> list[MagicMock]:
            proc = MagicMock()
            type(proc).info = property(
                lambda self: (_ for _ in ()).throw(psutil.ZombieProcess(1234))
            )
            return [proc]

        with patch("psutil.process_iter", mock_iter):
            collector = ProcessCollector()
            result = await collector.collect()

        # Should return empty list without raising
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_collect_handles_none_info(self) -> None:
        """Test that processes with None info are skipped."""
        mock_proc = MagicMock()
        mock_proc.info = None

        with patch("psutil.process_iter", return_value=[mock_proc]):
            collector = ProcessCollector()
            result = await collector.collect()

        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_collect_handles_empty_cmdline(self) -> None:
        """Test that empty cmdline list results in None."""
        MockMemInfo = namedtuple("MockMemInfo", ["rss", "vms"])
        mock_proc_info = {
            "pid": 1,
            "name": "test",
            "username": "user",
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_info": MockMemInfo(rss=0, vms=0),
            "status": "sleeping",
            "create_time": 0.0,
            "cmdline": [],
            "num_threads": 1,
        }

        mock_proc = MagicMock()
        mock_proc.info = mock_proc_info

        with patch("psutil.process_iter", return_value=[mock_proc]):
            collector = ProcessCollector()
            result = await collector.collect()

        assert result.processes[0].cmdline is None

    @pytest.mark.asyncio
    async def test_collect_running_count(self) -> None:
        """Test that running_count is calculated correctly."""
        MockMemInfo = namedtuple("MockMemInfo", ["rss", "vms"])

        running_proc = MagicMock()
        running_proc.info = {
            "pid": 1,
            "name": "running",
            "username": "",
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_info": MockMemInfo(0, 0),
            "status": psutil.STATUS_RUNNING,
            "create_time": 0.0,
            "cmdline": None,
            "num_threads": 1,
        }

        sleeping_proc = MagicMock()
        sleeping_proc.info = {
            "pid": 2,
            "name": "sleeping",
            "username": "",
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_info": MockMemInfo(0, 0),
            "status": psutil.STATUS_SLEEPING,
            "create_time": 0.0,
            "cmdline": None,
            "num_threads": 1,
        }

        with patch("psutil.process_iter", return_value=[running_proc, sleeping_proc]):
            collector = ProcessCollector()
            result = await collector.collect()

        assert result.total_count == 2
        assert result.running_count == 1


# ============================================================================
# ProcessPane Plugin Tests
# ============================================================================


class TestProcessPane:
    """Tests for ProcessPane plugin."""

    def test_pane_attributes(self) -> None:
        """Test pane class attributes."""
        pane = ProcessPane()
        assert pane.name == "processes"
        assert pane.display_name == "Processes"
        assert pane.version == "0.1.0"
        assert pane.default_refresh_interval == 2.0

    def test_pane_is_pane_plugin(self) -> None:
        """Test that ProcessPane is a PanePlugin."""
        from uptop.plugin_api import PanePlugin

        pane = ProcessPane()
        assert isinstance(pane, PanePlugin)

    def test_get_plugin_type(self) -> None:
        """Test that ProcessPane returns PANE type."""
        assert ProcessPane.get_plugin_type() == PluginType.PANE

    def test_get_schema(self) -> None:
        """Test that get_schema returns ProcessListData."""
        pane = ProcessPane()
        assert pane.get_schema() == ProcessListData

    def test_get_metadata(self) -> None:
        """Test metadata generation."""
        metadata = ProcessPane.get_metadata()
        assert metadata.name == "processes"
        assert metadata.display_name == "Processes"
        assert metadata.plugin_type == PluginType.PANE

    def test_initialize(self) -> None:
        """Test pane initialization."""
        pane = ProcessPane()
        pane.initialize({"custom": "config"})

        assert pane._initialized is True
        assert pane.config == {"custom": "config"}

    def test_shutdown(self) -> None:
        """Test pane shutdown."""
        pane = ProcessPane()
        pane.initialize()
        pane.shutdown()

        assert pane._initialized is False

    @pytest.mark.asyncio
    async def test_collect_data(self) -> None:
        """Test collect_data returns ProcessListData."""
        pane = ProcessPane()
        result = await pane.collect_data()

        assert isinstance(result, ProcessListData)
        assert result.total_count >= 0

    def test_render_tui_with_valid_data(self) -> None:
        """Test render_tui with valid ProcessListData."""
        pane = ProcessPane()
        data = ProcessListData(
            total_count=10,
            running_count=3,
            source="test",
        )

        widget = pane.render_tui(data)

        from uptop.tui.panes.process_widget import ProcessWidget

        assert isinstance(widget, ProcessWidget)
        assert hasattr(widget, "update_data")

    def test_render_tui_with_invalid_data(self) -> None:
        """Test render_tui with invalid data type."""
        pane = ProcessPane()

        # Create a different MetricData type
        class OtherData(MetricData):
            pass

        invalid_data = OtherData(source="test")
        widget = pane.render_tui(invalid_data)

        from textual.widgets import Label

        assert isinstance(widget, Label)


# ============================================================================
# Integration Tests
# ============================================================================


class TestProcessPaneIntegration:
    """Integration tests for the process pane."""

    @pytest.mark.asyncio
    async def test_full_collection_cycle(self) -> None:
        """Test a complete collection and render cycle."""
        pane = ProcessPane()
        pane.initialize()

        try:
            # Collect data
            data = await pane.collect_data()
            assert isinstance(data, ProcessListData)

            # Render the data
            widget = pane.render_tui(data)
            assert widget is not None

            # Verify schema
            schema = pane.get_schema()
            assert schema == ProcessListData
        finally:
            pane.shutdown()

    @pytest.mark.asyncio
    async def test_safe_collect_with_collector(self) -> None:
        """Test safe_collect wrapper on the collector."""
        collector = ProcessCollector()
        result = await collector.safe_collect()

        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, ProcessListData)
        assert result.collector_name == "process_collector"
        assert result.collection_time_ms >= 0
