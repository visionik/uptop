"""Ping Pane Plugin for uptop.

This module provides the ping monitoring pane which displays:
- Per-host ping latencies (current, min, avg, max)
- Packet loss percentages
- Status indicators (ok/warning/critical/unreachable)
- Latency sparkline history
- Jitter calculations
- Consecutive failure tracking

The plugin uses system ping commands via subprocess and handles gracefully
hosts that are unreachable or have DNS resolution failures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uptop.collectors.ping_collector import PingCollector
from uptop.models.base import DisplayMode, MetricData
from uptop.plugin_api.base import PanePlugin
from uptop.plugins.ping_models import PingData

if TYPE_CHECKING:
    from textual.widget import Widget


class PingPane(PanePlugin):
    """Ping monitoring pane plugin.

    Displays real-time network latency and availability metrics for
    configured hosts using ICMP ping.

    Class Attributes:
        name: Plugin identifier
        display_name: Human-readable name for UI
        version: Plugin version
        description: Brief description of functionality
        default_refresh_interval: Seconds between data collection
    """

    name: str = "ping"
    display_name: str = "Ping Monitor"
    version: str = "0.1.0"
    description: str = "Network latency and availability monitoring via ICMP ping"
    default_refresh_interval: float = 1.0

    def __init__(self) -> None:
        """Initialize the ping pane plugin."""
        super().__init__()
        self._collector: PingCollector | None = None
        self._cached_widget = None  # Cache widget to preserve state

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration (unused, loads from file)
        """
        from uptop.config.loader import load_config
        from uptop.plugins.ping_config import PingPluginConfig

        super().initialize(config)

        # Load ping config from the uptop config file
        try:
            uptop_config = load_config()
            if hasattr(uptop_config, "ping"):
                ping_config = uptop_config.ping
            else:
                # No ping config, use defaults
                ping_config = PingPluginConfig()
        except Exception:
            # Config load failed, use defaults
            ping_config = PingPluginConfig()

        self._collector = PingCollector(ping_config)

    def shutdown(self) -> None:
        """Clean up plugin resources."""
        if self._collector:
            self._collector.shutdown()
            self._collector = None
        self._cached_widget = None
        super().shutdown()

    async def collect_data(self) -> PingData:
        """Collect current ping data for all configured hosts.

        Returns:
            PingData with ping results for all hosts

        Raises:
            RuntimeError: If collector is not initialized
        """
        if self._collector is None:
            # Initialize collector if not already done
            from uptop.plugins.ping_config import PingPluginConfig

            self._collector = PingCollector(PingPluginConfig())

        return await self._collector.collect()

    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> Widget:
        """Render collected data as a Textual widget.

        Caches the widget instance to preserve state across refreshes.

        Args:
            data: The PingData from the most recent collection
            size: Optional (width, height) in cells (currently unused)
            mode: Optional DisplayMode for rendering detail level

        Returns:
            A Textual Widget to display in the pane
        """
        # Import here to avoid circular imports and allow running without textual
        from textual.widgets import Label

        from uptop.tui.panes.ping_widget import PingWidget

        if not isinstance(data, PingData):
            return Label("Invalid ping data")

        # Reuse cached widget to preserve state
        if self._cached_widget is None:
            self._cached_widget = PingWidget()

        self._cached_widget.update_data(data, mode)
        return self._cached_widget

    def get_schema(self) -> type[PingData]:
        """Return the Pydantic model class for this plugin's data.

        Returns:
            The PingData class
        """
        return PingData
