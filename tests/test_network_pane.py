"""Tests for the Network pane plugin."""

from collections import namedtuple
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
import pytest

from uptop.models import MetricData, MetricType, PluginType, get_metric_type
from uptop.plugins.network import (
    ConnectionData,
    NetworkCollector,
    NetworkData,
    NetworkInterfaceData,
    NetworkPane,
    _format_bytes,
    _format_rate,
)

# Mock types for psutil
MockNetIO = namedtuple(
    "snetio",
    [
        "bytes_sent",
        "bytes_recv",
        "packets_sent",
        "packets_recv",
        "errin",
        "errout",
        "dropin",
        "dropout",
    ],
)
MockIfStats = namedtuple("snicstats", ["isup", "duplex", "speed", "mtu"])
MockAddr = namedtuple("addr", ["ip", "port"])


class MockConnection:
    """Mock psutil connection object."""

    def __init__(
        self,
        family_name: str = "AF_INET",
        type_name: str = "SOCK_STREAM",
        laddr: tuple[str, int] | None = None,
        raddr: tuple[str, int] | None = None,
        status: str = "ESTABLISHED",
        pid: int | None = None,
    ) -> None:
        self.family = MagicMock()
        self.family.name = family_name
        self.type = MagicMock()
        self.type.name = type_name
        self.laddr = MockAddr(*laddr) if laddr else None
        self.raddr = MockAddr(*raddr) if raddr else None
        self.status = status
        self.pid = pid


class TestNetworkInterfaceData:
    """Tests for NetworkInterfaceData model."""

    def test_valid_interface(self) -> None:
        """Test creating a valid interface data object."""
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=100.0,
            bandwidth_down=200.0,
        )
        assert iface.name == "eth0"
        assert iface.bytes_sent == 1000
        assert iface.bandwidth_up == 100.0

    def test_metric_types(self) -> None:
        """Test that metric types are correctly annotated."""
        assert get_metric_type(NetworkInterfaceData, "bytes_sent") == MetricType.COUNTER
        assert get_metric_type(NetworkInterfaceData, "bytes_recv") == MetricType.COUNTER
        assert get_metric_type(NetworkInterfaceData, "packets_sent") == MetricType.COUNTER
        assert get_metric_type(NetworkInterfaceData, "errors_in") == MetricType.COUNTER
        assert get_metric_type(NetworkInterfaceData, "bandwidth_up") == MetricType.GAUGE
        assert get_metric_type(NetworkInterfaceData, "bandwidth_down") == MetricType.GAUGE

    def test_default_is_up(self) -> None:
        """Test that is_up defaults to True."""
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
        )
        assert iface.is_up is True

    def test_bytes_must_be_non_negative(self) -> None:
        """Test that negative byte counts are rejected."""
        with pytest.raises(ValidationError):
            NetworkInterfaceData(
                name="eth0",
                bytes_sent=-1,
                bytes_recv=0,
                packets_sent=0,
                packets_recv=0,
                errors_in=0,
                errors_out=0,
                drops_in=0,
                drops_out=0,
                bandwidth_up=0.0,
                bandwidth_down=0.0,
            )


class TestConnectionData:
    """Tests for ConnectionData model."""

    def test_valid_connection(self) -> None:
        """Test creating a valid connection data object."""
        conn = ConnectionData(
            family="IPv4",
            type="TCP",
            local_addr="127.0.0.1:8080",
            remote_addr="192.168.1.1:443",
            status="ESTABLISHED",
            pid=1234,
        )
        assert conn.family == "IPv4"
        assert conn.type == "TCP"
        assert conn.status == "ESTABLISHED"

    def test_defaults(self) -> None:
        """Test default values."""
        conn = ConnectionData(family="IPv4", type="TCP", local_addr="0.0.0.0:80")
        assert conn.remote_addr == ""
        assert conn.status == ""
        assert conn.pid is None


class TestNetworkData:
    """Tests for NetworkData model."""

    def test_empty_network_data(self) -> None:
        """Test creating empty network data."""
        data = NetworkData()
        assert data.interfaces == []
        assert data.connections == []
        assert data.interface_count == 0
        assert data.connection_count == 0

    def test_interface_count(self) -> None:
        """Test interface_count property."""
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
        )
        data = NetworkData(interfaces=[iface])
        assert data.interface_count == 1

    def test_get_interface(self) -> None:
        """Test get_interface method."""
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
        )
        data = NetworkData(interfaces=[iface])

        result = data.get_interface("eth0")
        assert result is not None
        assert result.bytes_sent == 1000

        assert data.get_interface("nonexistent") is None

    def test_metric_types(self) -> None:
        """Test that metric types are correctly annotated."""
        assert get_metric_type(NetworkData, "total_bytes_sent") == MetricType.COUNTER
        assert get_metric_type(NetworkData, "total_bytes_recv") == MetricType.COUNTER
        assert get_metric_type(NetworkData, "total_bandwidth_up") == MetricType.GAUGE
        assert get_metric_type(NetworkData, "total_bandwidth_down") == MetricType.GAUGE


class TestNetworkCollector:
    """Tests for NetworkCollector."""

    def test_collector_attributes(self) -> None:
        """Test collector class attributes."""
        collector = NetworkCollector()
        assert collector.name == "network"
        assert collector.default_interval == 1.0

    def test_get_schema(self) -> None:
        """Test get_schema returns correct class."""
        collector = NetworkCollector()
        assert collector.get_schema() == NetworkData

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_collect_basic(self, mock_psutil: MagicMock) -> None:
        """Test basic collection with mocked psutil."""
        collector = NetworkCollector()

        mock_io = MockNetIO(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io}
        mock_psutil.net_if_stats.return_value = {
            "eth0": MockIfStats(isup=True, duplex=2, speed=1000, mtu=1500)
        }
        mock_psutil.net_connections.return_value = []

        data = await collector.collect()

        assert data.interface_count == 1
        assert data.interfaces[0].name == "eth0"
        assert data.interfaces[0].bytes_sent == 1000
        assert data.interfaces[0].is_up is True

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    @patch("uptop.plugins.network.time")
    async def test_bandwidth_calculation(
        self, mock_time: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test bandwidth rate calculation between collections."""
        collector = NetworkCollector()

        # First collection at time 0
        mock_time.monotonic.return_value = 0.0
        mock_io_1 = MockNetIO(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io_1}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.net_connections.return_value = []

        data1 = await collector.collect()
        # First collection should have 0 bandwidth (no baseline)
        assert data1.interfaces[0].bandwidth_up == 0.0
        assert data1.interfaces[0].bandwidth_down == 0.0

        # Second collection at time 1.0 (1 second later)
        mock_time.monotonic.return_value = 1.0
        mock_io_2 = MockNetIO(
            bytes_sent=2000,  # +1000 bytes
            bytes_recv=4000,  # +2000 bytes
            packets_sent=20,
            packets_recv=40,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io_2}

        data2 = await collector.collect()
        # Should calculate 1000 bytes/sec up, 2000 bytes/sec down
        assert data2.interfaces[0].bandwidth_up == 1000.0
        assert data2.interfaces[0].bandwidth_down == 2000.0

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_collect_connections(self, mock_psutil: MagicMock) -> None:
        """Test connection collection."""
        collector = NetworkCollector()

        mock_psutil.net_io_counters.return_value = {}
        mock_psutil.net_if_stats.return_value = {}

        mock_conn = MockConnection(
            laddr=("127.0.0.1", 8080),
            raddr=("192.168.1.1", 443),
            status="ESTABLISHED",
            pid=1234,
        )
        mock_psutil.net_connections.return_value = [mock_conn]

        data = await collector.collect()

        assert data.connection_count == 1
        assert data.connections[0].local_addr == "127.0.0.1:8080"
        assert data.connections[0].remote_addr == "192.168.1.1:443"
        assert data.connections[0].status == "ESTABLISHED"
        assert data.connections[0].pid == 1234

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_collect_connections_access_denied(self, mock_psutil: MagicMock) -> None:
        """Test graceful handling of AccessDenied for connections."""
        import psutil as real_psutil

        collector = NetworkCollector()

        mock_psutil.net_io_counters.return_value = {}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.net_connections.side_effect = real_psutil.AccessDenied(pid=0)
        mock_psutil.AccessDenied = real_psutil.AccessDenied

        data = await collector.collect()
        assert data.connections == []

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_totals_calculation(self, mock_psutil: MagicMock) -> None:
        """Test that totals are correctly summed across interfaces."""
        collector = NetworkCollector()

        mock_io_1 = MockNetIO(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_io_2 = MockNetIO(
            bytes_sent=3000,
            bytes_recv=4000,
            packets_sent=30,
            packets_recv=40,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io_1, "eth1": mock_io_2}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.net_connections.return_value = []

        data = await collector.collect()

        assert data.total_bytes_sent == 4000  # 1000 + 3000
        assert data.total_bytes_recv == 6000  # 2000 + 4000


class TestNetworkPane:
    """Tests for NetworkPane plugin."""

    def test_pane_attributes(self) -> None:
        """Test pane class attributes."""
        pane = NetworkPane()
        assert pane.name == "network"
        assert pane.display_name == "Network Monitor"

    def test_plugin_type(self) -> None:
        """Test plugin type is PANE."""
        assert NetworkPane.get_plugin_type() == PluginType.PANE

    def test_get_schema(self) -> None:
        """Test get_schema returns NetworkData."""
        pane = NetworkPane()
        assert pane.get_schema() == NetworkData

    def test_initialize(self) -> None:
        """Test plugin initialization."""
        pane = NetworkPane()
        pane.initialize()
        assert pane._initialized is True
        assert pane._collector is not None

    def test_shutdown(self) -> None:
        """Test plugin shutdown."""
        pane = NetworkPane()
        pane.initialize()
        pane.shutdown()
        assert pane._initialized is False
        assert pane._collector is None

    def test_render_tui_with_valid_data(self) -> None:
        """Test TUI rendering with valid data."""
        pane = NetworkPane()
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=1000000,
            bytes_recv=2000000,
            packets_sent=1000,
            packets_recv=2000,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=1000.0,
            bandwidth_down=2000.0,
        )
        data = NetworkData(
            interfaces=[iface],
            total_bytes_sent=1000000,
            total_bytes_recv=2000000,
            total_bandwidth_up=1000.0,
            total_bandwidth_down=2000.0,
        )
        widget = pane.render_tui(data)

        from uptop.tui.panes.network_widget import NetworkWidget

        assert isinstance(widget, NetworkWidget)
        assert hasattr(widget, "update_data")

    def test_render_tui_with_invalid_data(self) -> None:
        """Test TUI rendering with invalid data type."""
        pane = NetworkPane()
        data = MetricData()
        widget = pane.render_tui(data)

        from textual.widgets import Label

        assert isinstance(widget, Label)

    def test_get_ai_help_docs(self) -> None:
        """Test AI help documentation."""
        pane = NetworkPane()
        docs = pane.get_ai_help_docs()
        assert "Network Monitor" in docs
        assert "bytes_sent" in docs
        assert "bandwidth" in docs

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_collect_data(self, mock_psutil: MagicMock) -> None:
        """Test collect_data method."""
        pane = NetworkPane()
        pane.initialize()

        mock_io = MockNetIO(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.net_connections.return_value = []

        data = await pane.collect_data()
        assert isinstance(data, NetworkData)

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_collect_data_auto_init(self, mock_psutil: MagicMock) -> None:
        """Test that collect_data auto-initializes collector."""
        pane = NetworkPane()
        # Don't call initialize()

        mock_io = MockNetIO(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io}
        mock_psutil.net_if_stats.return_value = {}
        mock_psutil.net_connections.return_value = []

        await pane.collect_data()
        assert pane._collector is not None

    def test_initialize_with_config(self) -> None:
        """Test initialization with config."""
        pane = NetworkPane()
        pane.initialize({"interval": 2.0})
        assert pane._collector is not None
        assert pane.config == {"interval": 2.0}


class TestFormatFunctions:
    """Tests for formatting helper functions."""

    def test_format_bytes(self) -> None:
        """Test byte formatting."""
        assert _format_bytes(0) == "0.0 B"
        assert _format_bytes(500) == "500.0 B"
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1024 * 1024) == "1.0 MB"
        assert _format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        assert _format_bytes(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_format_rate(self) -> None:
        """Test rate formatting."""
        assert _format_rate(1024) == "1.0 KB/s"
        assert _format_rate(1024 * 1024) == "1.0 MB/s"


class TestNetworkCollectorEdgeCases:
    """Additional edge case tests for NetworkCollector."""

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_interface_down(self, mock_psutil: MagicMock) -> None:
        """Test handling of interface that is down."""
        collector = NetworkCollector()

        mock_io = MockNetIO(
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io}
        mock_psutil.net_if_stats.return_value = {
            "eth0": MockIfStats(isup=False, duplex=0, speed=0, mtu=1500)
        }
        mock_psutil.net_connections.return_value = []

        data = await collector.collect()
        assert data.interfaces[0].is_up is False

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_if_stats_exception(self, mock_psutil: MagicMock) -> None:
        """Test graceful handling of net_if_stats exception."""
        collector = NetworkCollector()

        mock_io = MockNetIO(
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=10,
            packets_recv=20,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )
        mock_psutil.net_io_counters.return_value = {"eth0": mock_io}
        mock_psutil.net_if_stats.side_effect = RuntimeError("Stats unavailable")
        mock_psutil.net_connections.return_value = []

        data = await collector.collect()
        # Should still work, interface defaults to is_up=True
        assert data.interfaces[0].is_up is True

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_connection_without_remote(self, mock_psutil: MagicMock) -> None:
        """Test connection without remote address (listening socket)."""
        collector = NetworkCollector()

        mock_psutil.net_io_counters.return_value = {}
        mock_psutil.net_if_stats.return_value = {}

        mock_conn = MockConnection(
            laddr=("0.0.0.0", 80),
            raddr=None,
            status="LISTEN",
            pid=1234,
        )
        mock_psutil.net_connections.return_value = [mock_conn]

        data = await collector.collect()

        assert data.connections[0].local_addr == "0.0.0.0:80"
        assert data.connections[0].remote_addr == ""
        assert data.connections[0].status == "LISTEN"

    @pytest.mark.asyncio
    @patch("uptop.plugins.network.psutil")
    async def test_udp_connection(self, mock_psutil: MagicMock) -> None:
        """Test UDP connection handling."""
        collector = NetworkCollector()

        mock_psutil.net_io_counters.return_value = {}
        mock_psutil.net_if_stats.return_value = {}

        mock_conn = MockConnection(
            family_name="AF_INET",
            type_name="SOCK_DGRAM",
            laddr=("0.0.0.0", 53),
            status="",
        )
        mock_psutil.net_connections.return_value = [mock_conn]

        data = await collector.collect()

        assert data.connections[0].type == "UDP"
