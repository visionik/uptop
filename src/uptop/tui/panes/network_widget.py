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
from textual.widgets import DataTable

from uptop.plugins.network import NetworkData, NetworkInterfaceData


def format_bytes(bytes_val: int | float) -> str:
    """Format bytes value with appropriate unit (KB or larger).

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string like "1.2GB" or "456KB" (no space, never plain bytes)
    """
    # Always convert to at least KB
    kb_val = bytes_val / 1024.0

    for unit in ["KB", "MB", "GB", "TB"]:
        if abs(kb_val) < 1024.0:
            return f"{kb_val:.1f}{unit}"
        kb_val /= 1024.0
    return f"{kb_val:.1f}PB"


def format_count(value: int) -> str:
    """Format a count value with appropriate suffix.

    Args:
        value: The count value (packets, errors, drops, etc.)

    Returns:
        Formatted string:
        - 0-999: plain number (0, 1, 999)
        - 1K-9.9K: one decimal (1.0K, 9.9K)
        - 10K-999.9K: one decimal (10.0K, 999.9K)
        - 1M-999.9M: one decimal (1.0M, 999.9M)
        - 1B+: one decimal (1.0B, etc.)
    """
    if value < 1000:
        return str(value)
    if value < 1_000_000:
        return f"{value / 1000:.1f}K"
    if value < 1_000_000_000:
        return f"{value / 1_000_000:.1f}M"
    return f"{value / 1_000_000_000:.1f}B"


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

    NetworkWidget #interface-table {
        width: 100%;
        height: 1fr;
        scrollbar-size: 1 1;
    }

    NetworkWidget #summary-table {
        width: 100%;
        height: 1;
        scrollbar-size: 0 0;
        background: $surface;
    }

    NetworkWidget #summary-table.has-errors {
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
        """Compose the widget with a data table and summary row."""
        yield DataTable(id="interface-table")
        yield DataTable(id="summary-table")

    def on_mount(self) -> None:
        """Set up the data table when the widget is mounted."""
        table = self.query_one("#interface-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns to interface table
        table.add_column("Interface", key="name", width=12)
        table.add_column("◐", key="status", width=1)
        table.add_column("TX Now", key="tx_rate", width=7)
        table.add_column("RX Now", key="rx_rate", width=7)
        table.add_column("TX Sum", key="tx_total", width=7)
        table.add_column("RX Sum", key="rx_total", width=7)
        table.add_column("⚠", key="errors", width=7)
        table.add_column("⇣", key="drops", width=7)

        # Set up summary table with same columns (no header)
        summary = self.query_one("#summary-table", DataTable)
        summary.show_header = False
        summary.show_cursor = False
        summary.add_column("name", width=12)
        summary.add_column("status", width=1)
        summary.add_column("tx_rate", width=7)
        summary.add_column("rx_rate", width=7)
        summary.add_column("tx_total", width=7)
        summary.add_column("rx_total", width=7)
        summary.add_column("errors", width=7)
        summary.add_column("drops", width=7)

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
            Tuple of formatted column values (rates/totals right-justified)
        """
        status = "●" if iface.is_up else "○"
        tx_rate = format_bytes(iface.bandwidth_up).rjust(7)
        rx_rate = format_bytes(iface.bandwidth_down).rjust(7)
        tx_total = format_bytes(iface.bytes_sent).rjust(7)
        rx_total = format_bytes(iface.bytes_recv).rjust(7)

        # Format errors (combine in/out)
        total_errors = iface.errors_in + iface.errors_out
        errors = format_count(total_errors)

        # Format drops (combine in/out)
        total_drops = iface.drops_in + iface.drops_out
        drops = format_count(total_drops)

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

        # Save scroll position and cursor before clearing
        saved_scroll_x = table.scroll_x
        saved_scroll_y = table.scroll_y
        saved_cursor_row = table.cursor_row

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

        # Update summary line
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary row with totals matching the table columns."""
        if self.data is None:
            return

        try:
            summary = self.query_one("#summary-table", DataTable)
        except Exception:
            return  # Widget not ready

        # Calculate totals
        total_bytes_sent = sum(iface.bytes_sent for iface in self.data.interfaces)
        total_bytes_recv = sum(iface.bytes_recv for iface in self.data.interfaces)
        total_errors = sum(iface.errors_in + iface.errors_out for iface in self.data.interfaces)
        total_drops = sum(iface.drops_in + iface.drops_out for iface in self.data.interfaces)

        # Format row data to match interface table columns
        row_data = (
            "TOTAL",  # Interface name
            " ",  # Status (empty)
            format_bytes(self.data.total_bandwidth_up).rjust(7),  # TX Now
            format_bytes(self.data.total_bandwidth_down).rjust(7),  # RX Now
            format_bytes(total_bytes_sent).rjust(7),  # TX Sum
            format_bytes(total_bytes_recv).rjust(7),  # RX Sum
            format_count(total_errors),  # Errors
            format_count(total_drops),  # Drops
        )

        # Clear and add the summary row
        summary.clear()
        summary.add_row(*row_data, key="total")

        # Update CSS class for warning styling
        has_issues = total_errors > 0 or total_drops > 0
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
