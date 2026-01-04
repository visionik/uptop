"""Network Pane Plugin for uptop.

This module provides the Network monitoring pane which displays:
- Per-interface network statistics (bytes, packets, errors, drops)
- Calculated bandwidth rates (bytes/sec upload and download)
- Active network connections (TCP/UDP with state and addresses)

The plugin uses psutil for all data collection and calculates
bandwidth rates by tracking deltas between collection intervals.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import psutil
from pydantic import BaseModel, ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import MetricData, counter_field, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget


class NetworkInterfaceData(BaseModel):
    """Data model for a single network interface.

    Contains both cumulative counters (bytes/packets sent/received)
    and calculated gauge metrics (current bandwidth rates).

    Attributes:
        name: Interface name (e.g., "eth0", "en0", "lo")
        bytes_sent: Total bytes transmitted (counter)
        bytes_recv: Total bytes received (counter)
        packets_sent: Total packets transmitted (counter)
        packets_recv: Total packets received (counter)
        errors_in: Total receive errors (counter)
        errors_out: Total transmit errors (counter)
        drops_in: Total incoming packets dropped (counter)
        drops_out: Total outgoing packets dropped (counter)
        bandwidth_up: Current upload rate in bytes/sec (gauge)
        bandwidth_down: Current download rate in bytes/sec (gauge)
        is_up: Whether the interface is up
    """

    # Use frozen=True for immutability
    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Interface name")
    bytes_sent: int = counter_field("Total bytes transmitted", ge=0)
    bytes_recv: int = counter_field("Total bytes received", ge=0)
    packets_sent: int = counter_field("Total packets transmitted", ge=0)
    packets_recv: int = counter_field("Total packets received", ge=0)
    errors_in: int = counter_field("Receive errors", ge=0)
    errors_out: int = counter_field("Transmit errors", ge=0)
    drops_in: int = counter_field("Incoming packets dropped", ge=0)
    drops_out: int = counter_field("Outgoing packets dropped", ge=0)
    bandwidth_up: float = gauge_field("Current upload rate bytes/sec", ge=0.0)
    bandwidth_down: float = gauge_field("Current download rate bytes/sec", ge=0.0)
    is_up: bool = Field(default=True, description="Interface is up")


class ConnectionData(BaseModel):
    """Data model for a single network connection.

    Attributes:
        family: Address family (AF_INET, AF_INET6)
        type: Socket type (SOCK_STREAM for TCP, SOCK_DGRAM for UDP)
        local_addr: Local address (ip:port)
        remote_addr: Remote address (ip:port) or empty for listening
        status: Connection status (ESTABLISHED, LISTEN, TIME_WAIT, etc.)
        pid: Process ID owning the connection (None if not accessible)
    """

    # Use frozen=True for immutability
    model_config = ConfigDict(frozen=True)

    family: str = Field(..., description="Address family (IPv4/IPv6)")
    type: str = Field(..., description="Socket type (TCP/UDP)")
    local_addr: str = Field(..., description="Local address ip:port")
    remote_addr: str = Field(default="", description="Remote address ip:port")
    status: str = Field(default="", description="Connection status")
    pid: int | None = Field(default=None, description="Process ID")


class NetworkData(MetricData):
    """Aggregated network metrics for all interfaces and connections.

    This is the data model returned by NetworkCollector and consumed by NetworkPane.

    Attributes:
        interfaces: List of per-interface network data
        connections: List of active network connections
        total_bytes_sent: Sum of bytes sent across all interfaces (counter)
        total_bytes_recv: Sum of bytes received across all interfaces (counter)
        total_bandwidth_up: Sum of upload bandwidth across all interfaces (gauge)
        total_bandwidth_down: Sum of download bandwidth across all interfaces (gauge)
    """

    interfaces: list[NetworkInterfaceData] = Field(
        default_factory=list, description="Per-interface network data"
    )
    connections: list[ConnectionData] = Field(
        default_factory=list, description="Active network connections"
    )
    total_bytes_sent: int = counter_field("Total bytes sent across all interfaces", ge=0, default=0)
    total_bytes_recv: int = counter_field(
        "Total bytes received across all interfaces", ge=0, default=0
    )
    total_bandwidth_up: float = gauge_field("Total upload bandwidth bytes/sec", ge=0.0, default=0.0)
    total_bandwidth_down: float = gauge_field(
        "Total download bandwidth bytes/sec", ge=0.0, default=0.0
    )

    @property
    def interface_count(self) -> int:
        """Return the number of network interfaces."""
        return len(self.interfaces)

    @property
    def connection_count(self) -> int:
        """Return the number of active connections."""
        return len(self.connections)

    def get_interface(self, name: str) -> NetworkInterfaceData | None:
        """Get interface data by name."""
        for iface in self.interfaces:
            if iface.name == name:
                return iface
        return None


class NetworkCollector(DataCollector[NetworkData]):
    """Collector for network metrics using psutil.

    Gathers per-interface network statistics and active connections.
    Calculates bandwidth rates by tracking byte count deltas between
    collection intervals.

    Class Attributes:
        name: Collector identifier
        default_interval: Default collection interval in seconds
        timeout: Maximum time allowed for collection
    """

    name: str = "network"
    default_interval: float = 1.0
    timeout: float = 5.0

    def __init__(self) -> None:
        """Initialize the network collector."""
        super().__init__()
        # Track previous values for rate calculation
        self._prev_counters: dict[str, tuple[int, int]] = {}  # name -> (bytes_sent, bytes_recv)
        self._prev_time: float | None = None

    def _get_interface_stats(self) -> list[NetworkInterfaceData]:
        """Get network interface statistics with bandwidth calculation.

        Returns:
            List of NetworkInterfaceData for each interface
        """
        current_time = time.monotonic()
        io_counters = psutil.net_io_counters(pernic=True)

        # Try to get interface status (up/down)
        try:
            if_stats = psutil.net_if_stats()
        except Exception:
            if_stats = {}

        interfaces: list[NetworkInterfaceData] = []

        for name, counters in io_counters.items():
            # Calculate bandwidth rates
            bandwidth_up = 0.0
            bandwidth_down = 0.0

            if self._prev_time is not None and name in self._prev_counters:
                time_delta = current_time - self._prev_time
                if time_delta > 0:
                    prev_sent, prev_recv = self._prev_counters[name]
                    bytes_sent_delta = counters.bytes_sent - prev_sent
                    bytes_recv_delta = counters.bytes_recv - prev_recv

                    # Handle counter reset (e.g., interface restart)
                    if bytes_sent_delta >= 0:
                        bandwidth_up = bytes_sent_delta / time_delta
                    if bytes_recv_delta >= 0:
                        bandwidth_down = bytes_recv_delta / time_delta

            # Store current values for next calculation
            self._prev_counters[name] = (counters.bytes_sent, counters.bytes_recv)

            # Check if interface is up
            is_up = True
            if name in if_stats:
                is_up = if_stats[name].isup

            interfaces.append(
                NetworkInterfaceData(
                    name=name,
                    bytes_sent=counters.bytes_sent,
                    bytes_recv=counters.bytes_recv,
                    packets_sent=counters.packets_sent,
                    packets_recv=counters.packets_recv,
                    errors_in=counters.errin,
                    errors_out=counters.errout,
                    drops_in=counters.dropin,
                    drops_out=counters.dropout,
                    bandwidth_up=bandwidth_up,
                    bandwidth_down=bandwidth_down,
                    is_up=is_up,
                )
            )

        self._prev_time = current_time
        return interfaces

    def _get_connections(self) -> list[ConnectionData]:
        """Get active network connections.

        Returns:
            List of ConnectionData for each connection.
            Returns empty list if access is denied (requires privileges).
        """
        connections: list[ConnectionData] = []

        try:
            # Get all connections (TCP and UDP)
            net_connections = psutil.net_connections(kind="all")

            for conn in net_connections:
                # Format addresses
                local_addr = ""
                if conn.laddr:
                    local_addr = f"{conn.laddr.ip}:{conn.laddr.port}"

                remote_addr = ""
                if conn.raddr:
                    remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}"

                # Determine family and type strings
                family = "IPv4" if conn.family.name == "AF_INET" else "IPv6"
                sock_type = "TCP" if conn.type.name == "SOCK_STREAM" else "UDP"

                connections.append(
                    ConnectionData(
                        family=family,
                        type=sock_type,
                        local_addr=local_addr,
                        remote_addr=remote_addr,
                        status=conn.status if hasattr(conn, "status") else "",
                        pid=conn.pid,
                    )
                )

        except psutil.AccessDenied:
            # Need elevated permissions for full connection list
            pass
        except Exception:
            # Handle other errors gracefully
            pass

        return connections

    async def collect(self) -> NetworkData:
        """Collect current network metrics.

        Returns:
            NetworkData with per-interface stats, connections, and totals.
        """
        interfaces = self._get_interface_stats()
        connections = self._get_connections()

        # Calculate totals
        total_bytes_sent = sum(iface.bytes_sent for iface in interfaces)
        total_bytes_recv = sum(iface.bytes_recv for iface in interfaces)
        total_bandwidth_up = sum(iface.bandwidth_up for iface in interfaces)
        total_bandwidth_down = sum(iface.bandwidth_down for iface in interfaces)

        return NetworkData(
            source=self.name,
            interfaces=interfaces,
            connections=connections,
            total_bytes_sent=total_bytes_sent,
            total_bytes_recv=total_bytes_recv,
            total_bandwidth_up=total_bandwidth_up,
            total_bandwidth_down=total_bandwidth_down,
        )

    def get_schema(self) -> type[NetworkData]:
        """Return the Pydantic model class for this collector data.

        Returns:
            The NetworkData class
        """
        return NetworkData


def _format_bytes(bytes_val: int | float) -> str:
    """Format bytes value with appropriate unit.

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string like "1.23 GB" or "456 KB"
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


def _format_rate(bytes_per_sec: float) -> str:
    """Format bandwidth rate with appropriate unit.

    Args:
        bytes_per_sec: Bytes per second

    Returns:
        Formatted string like "1.23 MB/s" or "456 KB/s"
    """
    return f"{_format_bytes(bytes_per_sec)}/s"


class NetworkPane(PanePlugin):
    """Network monitoring pane plugin.

    Displays real-time network metrics including per-interface
    statistics, bandwidth rates, and active connections.

    Class Attributes:
        name: Plugin identifier
        display_name: Human-readable name for UI
        version: Plugin version
        description: Brief description of functionality
        default_refresh_interval: Seconds between data collection
    """

    name: str = "network"
    display_name: str = "Network Monitor"
    version: str = "0.1.0"
    description: str = "Real-time network interface statistics and connection monitoring"
    default_refresh_interval: float = 1.0

    def __init__(self) -> None:
        """Initialize the network pane plugin."""
        super().__init__()
        self._collector: NetworkCollector | None = None

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration
        """
        super().initialize(config)
        self._collector = NetworkCollector()
        if config:
            self._collector.initialize(config)
        else:
            self._collector.initialize()

    def shutdown(self) -> None:
        """Clean up plugin resources."""
        if self._collector:
            self._collector.shutdown()
            self._collector = None
        super().shutdown()

    async def collect_data(self) -> NetworkData:
        """Collect current network data.

        Returns:
            NetworkData with current network metrics

        Raises:
            RuntimeError: If collector is not initialized
        """
        if self._collector is None:
            # Initialize collector if not already done
            self._collector = NetworkCollector()
            self._collector.initialize()

        return await self._collector.collect()

    def render_tui(self, data: MetricData) -> Widget:
        """Render collected data as a Textual widget.

        Args:
            data: The NetworkData from the most recent collection

        Returns:
            A Textual Widget to display in the pane
        """
        # Import here to avoid circular imports and allow running without textual
        from textual.widgets import Label

        from uptop.tui.panes.network_widget import NetworkWidget

        if not isinstance(data, NetworkData):
            return Label("Invalid network data")

        # Create and populate the NetworkWidget with real data
        widget = NetworkWidget()
        widget.update_data(data)
        return widget

    def get_schema(self) -> type[NetworkData]:
        """Return the Pydantic model class for this pane data.

        Returns:
            The NetworkData class
        """
        return NetworkData

    def get_ai_help_docs(self) -> str:
        """Return markdown documentation for --ai-help output.

        Returns:
            Markdown-formatted string describing the plugin
        """
        return """## Network Monitor

The Network Monitor pane displays real-time network metrics:

### Metrics Collected
- **Per-Interface Statistics**:
  - Bytes sent/received (cumulative counters)
  - Packets sent/received (cumulative counters)
  - Errors and drops (cumulative counters)
  - Bandwidth up/down rates (calculated gauges in bytes/sec)
  - Interface status (up/down)

- **Active Connections** (requires elevated permissions on some systems):
  - Local and remote addresses (IP:port)
  - Connection type (TCP/UDP)
  - Connection status (ESTABLISHED, LISTEN, TIME_WAIT, etc.)
  - Process ID (when accessible)

### Configuration Options
- `interval`: Collection interval in seconds (default: 1.0)

### Metric Types
- **Counters**: bytes_sent, bytes_recv, packets_sent, packets_recv, errors_*, drops_*
- **Gauges**: bandwidth_up, bandwidth_down

### Notes
- Bandwidth rates are calculated from byte count deltas between collections
- First collection shows 0 bandwidth (no previous baseline)
- Connection list may be empty without elevated permissions
- Loopback interface (lo/lo0) is included in statistics
"""
