"""Network Widget for uptop TUI.

This module provides a Textual widget for displaying network interface statistics
and connection information. The widget shows:
- Per-interface statistics (name, bytes sent/recv, packets, errors, drops)
- Bandwidth rates in human-readable format (auto-scaled KB/s, MB/s, etc.)
- Active connection count
- Visual indicators for interfaces with traffic and errors
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Static

from uptop.plugins.network import NetworkData, NetworkInterfaceData


def format_bytes(bytes_val: int | float) -> str:
    """Format bytes value with appropriate unit.

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string like "1.2 GB" or "456 KB"
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


def format_rate(bytes_per_sec: float) -> str:
    """Format bandwidth rate with appropriate unit.

    Args:
        bytes_per_sec: Bytes per second

    Returns:
        Formatted string like "1.2 MB/s" or "456 KB/s"
    """
    return f"{format_bytes(bytes_per_sec)}/s"


class NetworkWidget(Widget):
    """Widget for displaying network interface statistics.

    Displays a table of network interfaces with their statistics including:
    - Interface name and status (up/down)
    - Bytes sent and received with bandwidth rates
    - Packet counts
    - Error and drop counts (highlighted in warning color if > 0)
    - Active connection count summary

    Attributes:
        data: The NetworkData object containing interface and connection info
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    NetworkWidget {
        width: 100%;
        height: 100%;
        padding: 0;
    }

    NetworkWidget DataTable {
        width: 100%;
        height: 1fr;
    }

    NetworkWidget .summary-line {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface;
    }

    NetworkWidget .summary-line.has-errors {
        color: $warning;
    }
    """

    data: reactive[NetworkData | None] = reactive(None)

    def __init__(
        self,
        data: NetworkData | None = None,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the network widget.

        Args:
            data: Initial NetworkData to display
            name: Widget name for CSS/querying
            id: Widget ID for CSS/querying
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.data = data

    def compose(self) -> ComposeResult:
        """Compose the widget with a data table and summary line."""
        yield DataTable(id="interface-table")
        yield Static("", id="summary-line", classes="summary-line")

    def on_mount(self) -> None:
        """Set up the data table when the widget is mounted."""
        table = self.query_one("#interface-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("Interface", key="name", width=12)
        table.add_column("Status", key="status", width=6)
        table.add_column("TX Rate", key="tx_rate", width=12)
        table.add_column("RX Rate", key="rx_rate", width=12)
        table.add_column("TX Total", key="tx_total", width=10)
        table.add_column("RX Total", key="rx_total", width=10)
        table.add_column("Errors", key="errors", width=8)
        table.add_column("Drops", key="drops", width=8)

        # Populate with initial data if available
        if self.data is not None:
            self._update_table()

    def watch_data(self, new_data: NetworkData | None) -> None:
        """React to data changes.

        Args:
            new_data: The new NetworkData value
        """
        if self.is_mounted and new_data is not None:
            self._update_table()

    def _format_interface_row(
        self, iface: NetworkInterfaceData
    ) -> tuple[str, str, str, str, str, str, str, str]:
        """Format interface data as a table row.

        Args:
            iface: The interface data to format

        Returns:
            Tuple of formatted column values
        """
        status = "UP" if iface.is_up else "DOWN"
        tx_rate = format_rate(iface.bandwidth_up)
        rx_rate = format_rate(iface.bandwidth_down)
        tx_total = format_bytes(iface.bytes_sent)
        rx_total = format_bytes(iface.bytes_recv)

        # Format errors (combine in/out)
        total_errors = iface.errors_in + iface.errors_out
        errors = str(total_errors) if total_errors > 0 else "-"

        # Format drops (combine in/out)
        total_drops = iface.drops_in + iface.drops_out
        drops = str(total_drops) if total_drops > 0 else "-"

        return (iface.name, status, tx_rate, rx_rate, tx_total, rx_total, errors, drops)

    def _has_traffic(self, iface: NetworkInterfaceData) -> bool:
        """Check if an interface has active traffic.

        Args:
            iface: The interface data to check

        Returns:
            True if the interface has bandwidth activity
        """
        return iface.bandwidth_up > 0 or iface.bandwidth_down > 0

    def _has_issues(self, iface: NetworkInterfaceData) -> bool:
        """Check if an interface has errors or drops.

        Args:
            iface: The interface data to check

        Returns:
            True if the interface has errors or drops
        """
        return (
            iface.errors_in > 0 or iface.errors_out > 0 or iface.drops_in > 0 or iface.drops_out > 0
        )

    def _update_table(self) -> None:
        """Update the data table with current data."""
        if self.data is None:
            return

        try:
            table = self.query_one("#interface-table", DataTable)
        except Exception:
            return  # Widget not ready

        # Clear existing rows
        table.clear()

        # Sort interfaces: active interfaces first, then by name
        sorted_interfaces = sorted(
            self.data.interfaces,
            key=lambda x: (not self._has_traffic(x), x.name.lower()),
        )

        # Add rows for each interface
        for iface in sorted_interfaces:
            row_data = self._format_interface_row(iface)
            table.add_row(*row_data, key=iface.name)

        # Update summary line
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary line with connection count and totals."""
        if self.data is None:
            return

        try:
            summary = self.query_one("#summary-line", Static)
        except Exception:
            return  # Widget not ready

        # Build summary text
        parts = []

        # Total bandwidth
        if self.data.total_bandwidth_up > 0 or self.data.total_bandwidth_down > 0:
            parts.append(
                f"Total: TX {format_rate(self.data.total_bandwidth_up)} / "
                f"RX {format_rate(self.data.total_bandwidth_down)}"
            )

        # Connection count
        parts.append(f"Connections: {self.data.connection_count}")

        # Error summary
        total_errors = sum(iface.errors_in + iface.errors_out for iface in self.data.interfaces)
        total_drops = sum(iface.drops_in + iface.drops_out for iface in self.data.interfaces)

        has_issues = total_errors > 0 or total_drops > 0
        if has_issues:
            parts.append(f"Errors: {total_errors}, Drops: {total_drops}")

        summary.update(" | ".join(parts))

        # Update CSS class for warning styling
        if has_issues:
            summary.add_class("has-errors")
        else:
            summary.remove_class("has-errors")

    def update_data(self, data: NetworkData) -> None:
        """Update the widget with new network data.

        This is the primary method for updating the widget display.

        Args:
            data: The new NetworkData to display
        """
        self.data = data
