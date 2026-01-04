"""Tests for the Network Widget."""

import pytest
from textual.widgets import DataTable, Static

from uptop.plugins.network import ConnectionData, NetworkData, NetworkInterfaceData
from uptop.tui.panes.network_widget import (
    NetworkWidget,
    format_bytes,
    format_rate,
)


class TestFormatBytes:
    """Tests for the format_bytes function."""

    def test_format_bytes_zero(self) -> None:
        """Test formatting zero bytes."""
        assert format_bytes(0) == "0.0 B"

    def test_format_bytes_small(self) -> None:
        """Test formatting small byte values."""
        assert format_bytes(100) == "100.0 B"
        assert format_bytes(500) == "500.0 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobyte values."""
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(10240) == "10.0 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabyte values."""
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1.5 * 1024 * 1024) == "1.5 MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabyte values."""
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"

    def test_format_bytes_terabytes(self) -> None:
        """Test formatting terabyte values."""
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_format_bytes_petabytes(self) -> None:
        """Test formatting petabyte values."""
        assert format_bytes(1024 * 1024 * 1024 * 1024 * 1024) == "1.0 PB"


class TestFormatRate:
    """Tests for the format_rate function."""

    def test_format_rate_zero(self) -> None:
        """Test formatting zero rate."""
        assert format_rate(0) == "0.0 B/s"

    def test_format_rate_kilobytes(self) -> None:
        """Test formatting kilobyte rates."""
        assert format_rate(1024) == "1.0 KB/s"

    def test_format_rate_megabytes(self) -> None:
        """Test formatting megabyte rates."""
        assert format_rate(1024 * 1024) == "1.0 MB/s"

    def test_format_rate_fractional(self) -> None:
        """Test formatting fractional rates."""
        assert format_rate(1.5 * 1024) == "1.5 KB/s"


class TestNetworkWidget:
    """Tests for NetworkWidget instantiation and basic functionality."""

    def test_widget_instantiation_no_data(self) -> None:
        """Test creating widget without data."""
        widget = NetworkWidget()
        assert widget.data is None

    def test_widget_instantiation_with_data(self) -> None:
        """Test creating widget with data."""
        data = NetworkData()
        widget = NetworkWidget(data=data)
        assert widget.data is data

    def test_widget_instantiation_with_id(self) -> None:
        """Test creating widget with custom id."""
        widget = NetworkWidget(id="my-network-widget")
        assert widget.id == "my-network-widget"

    def test_widget_instantiation_with_classes(self) -> None:
        """Test creating widget with custom classes."""
        widget = NetworkWidget(classes="custom-class")
        assert "custom-class" in widget.classes

    def test_update_data_method(self) -> None:
        """Test the update_data method."""
        widget = NetworkWidget()
        data = NetworkData()
        widget.update_data(data)
        assert widget.data is data

    def test_format_interface_row_basic(self) -> None:
        """Test formatting a basic interface row."""
        widget = NetworkWidget()
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=1024 * 1024,
            bytes_recv=2 * 1024 * 1024,
            packets_sent=100,
            packets_recv=200,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=1024.0,
            bandwidth_down=2048.0,
            is_up=True,
        )

        row = widget._format_interface_row(iface)

        assert row[0] == "eth0"  # name
        assert row[1] == "UP"  # status
        assert "1.0 KB/s" in row[2]  # tx_rate
        assert "2.0 KB/s" in row[3]  # rx_rate
        assert "1.0 MB" in row[4]  # tx_total
        assert "2.0 MB" in row[5]  # rx_total
        assert row[6] == "-"  # errors (none)
        assert row[7] == "-"  # drops (none)

    def test_format_interface_row_with_errors(self) -> None:
        """Test formatting an interface row with errors and drops."""
        widget = NetworkWidget()
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errors_in=5,
            errors_out=3,
            drops_in=2,
            drops_out=1,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
            is_up=True,
        )

        row = widget._format_interface_row(iface)

        assert row[6] == "8"  # errors: 5 + 3
        assert row[7] == "3"  # drops: 2 + 1

    def test_format_interface_row_down_status(self) -> None:
        """Test formatting an interface that is down."""
        widget = NetworkWidget()
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
            is_up=False,
        )

        row = widget._format_interface_row(iface)
        assert row[1] == "DOWN"

    def test_has_traffic_true(self) -> None:
        """Test _has_traffic with active traffic."""
        widget = NetworkWidget()
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
            bandwidth_up=100.0,
            bandwidth_down=0.0,
            is_up=True,
        )
        assert widget._has_traffic(iface) is True

    def test_has_traffic_false(self) -> None:
        """Test _has_traffic with no traffic."""
        widget = NetworkWidget()
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
            is_up=True,
        )
        assert widget._has_traffic(iface) is False

    def test_has_issues_with_errors(self) -> None:
        """Test _has_issues with errors."""
        widget = NetworkWidget()
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errors_in=1,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
            is_up=True,
        )
        assert widget._has_issues(iface) is True

    def test_has_issues_with_drops(self) -> None:
        """Test _has_issues with drops."""
        widget = NetworkWidget()
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errors_in=0,
            errors_out=0,
            drops_in=1,
            drops_out=0,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
            is_up=True,
        )
        assert widget._has_issues(iface) is True

    def test_has_issues_clean(self) -> None:
        """Test _has_issues with no issues."""
        widget = NetworkWidget()
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
            is_up=True,
        )
        assert widget._has_issues(iface) is False


class TestNetworkWidgetWithApp:
    """Tests for NetworkWidget rendering with Textual test framework."""

    @pytest.fixture
    def sample_network_data(self) -> NetworkData:
        """Create sample network data for testing."""
        iface1 = NetworkInterfaceData(
            name="eth0",
            bytes_sent=1024 * 1024 * 100,  # 100 MB
            bytes_recv=1024 * 1024 * 200,  # 200 MB
            packets_sent=10000,
            packets_recv=20000,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=1024 * 1024,  # 1 MB/s
            bandwidth_down=2 * 1024 * 1024,  # 2 MB/s
            is_up=True,
        )
        iface2 = NetworkInterfaceData(
            name="lo",
            bytes_sent=1024 * 10,
            bytes_recv=1024 * 10,
            packets_sent=100,
            packets_recv=100,
            errors_in=0,
            errors_out=0,
            drops_in=0,
            drops_out=0,
            bandwidth_up=0.0,
            bandwidth_down=0.0,
            is_up=True,
        )
        conn = ConnectionData(
            family="IPv4",
            type="TCP",
            local_addr="127.0.0.1:8080",
            remote_addr="192.168.1.1:443",
            status="ESTABLISHED",
            pid=1234,
        )
        return NetworkData(
            interfaces=[iface1, iface2],
            connections=[conn],
            total_bytes_sent=iface1.bytes_sent + iface2.bytes_sent,
            total_bytes_recv=iface1.bytes_recv + iface2.bytes_recv,
            total_bandwidth_up=iface1.bandwidth_up,
            total_bandwidth_down=iface1.bandwidth_down,
        )

    @pytest.fixture
    def sample_network_data_with_errors(self) -> NetworkData:
        """Create sample network data with errors for testing."""
        iface = NetworkInterfaceData(
            name="eth0",
            bytes_sent=1024 * 1024,
            bytes_recv=2 * 1024 * 1024,
            packets_sent=1000,
            packets_recv=2000,
            errors_in=10,
            errors_out=5,
            drops_in=3,
            drops_out=2,
            bandwidth_up=1024.0,
            bandwidth_down=2048.0,
            is_up=True,
        )
        return NetworkData(
            interfaces=[iface],
            connections=[],
            total_bytes_sent=iface.bytes_sent,
            total_bytes_recv=iface.bytes_recv,
            total_bandwidth_up=iface.bandwidth_up,
            total_bandwidth_down=iface.bandwidth_down,
        )

    @pytest.mark.asyncio
    async def test_widget_compose(self, sample_network_data: NetworkData) -> None:
        """Test that widget composes correctly."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NetworkWidget(data=sample_network_data, id="test-widget")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one("#test-widget", NetworkWidget)
            assert widget is not None

            # Check that DataTable exists
            table = widget.query_one("#interface-table", DataTable)
            assert table is not None

            # Check that summary line exists
            summary = widget.query_one("#summary-line", Static)
            assert summary is not None

    @pytest.mark.asyncio
    async def test_widget_table_columns(self, sample_network_data: NetworkData) -> None:
        """Test that the data table has correct columns."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NetworkWidget(data=sample_network_data, id="test-widget")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one("#test-widget", NetworkWidget)
            table = widget.query_one("#interface-table", DataTable)

            # Check column count using columns property
            assert len(table.columns) == 8

    @pytest.mark.asyncio
    async def test_widget_table_rows(self, sample_network_data: NetworkData) -> None:
        """Test that the data table has correct rows."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NetworkWidget(data=sample_network_data, id="test-widget")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one("#test-widget", NetworkWidget)
            table = widget.query_one("#interface-table", DataTable)

            # Should have 2 interfaces
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_widget_update_data(self, sample_network_data: NetworkData) -> None:
        """Test updating widget data."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NetworkWidget(id="test-widget")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one("#test-widget", NetworkWidget)

            # Initially no data
            table = widget.query_one("#interface-table", DataTable)
            assert table.row_count == 0

            # Update with data
            widget.update_data(sample_network_data)
            await pilot.pause()

            # Now should have rows
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_widget_empty_data(self) -> None:
        """Test widget with empty network data."""
        from textual.app import App

        empty_data = NetworkData()

        class TestApp(App):
            def compose(self):
                yield NetworkWidget(data=empty_data, id="test-widget")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one("#test-widget", NetworkWidget)
            table = widget.query_one("#interface-table", DataTable)

            # Should have no rows
            assert table.row_count == 0

    @pytest.mark.asyncio
    async def test_widget_sorts_active_interfaces_first(
        self, sample_network_data: NetworkData
    ) -> None:
        """Test that active interfaces are sorted first."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NetworkWidget(data=sample_network_data, id="test-widget")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one("#test-widget", NetworkWidget)
            table = widget.query_one("#interface-table", DataTable)

            # eth0 has traffic, lo does not
            # eth0 should be first despite "lo" coming before "eth0" alphabetically
            # Access the first row's key - the key is a RowKey object with value attribute
            row_keys = list(table.rows.keys())
            first_row_key = row_keys[0].value if hasattr(row_keys[0], "value") else str(row_keys[0])
            assert first_row_key == "eth0"
