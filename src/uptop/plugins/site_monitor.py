"""Site Monitor Plugin for uptop.

This module provides site uptime monitoring which displays:
- Whether a site (e.g., google.com) is up or down
- Response time in milliseconds
- HTTP status code
- Last check timestamp

The plugin uses httpx for HTTP requests with async support.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import DisplayMode, MetricData, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget


class SiteStatus(BaseModel):
    """Data model for a monitored site.

    Attributes:
        url: The URL being monitored
        is_up: Whether the site is responding
        status_code: HTTP status code (None if request failed)
        response_time_ms: Response time in milliseconds (None if request failed)
        last_check: Unix timestamp of last check
        error_message: Error message if request failed (None if successful)
    """

    model_config = ConfigDict(frozen=True)

    url: str = Field(..., description="URL being monitored")
    is_up: bool = Field(default=False, description="Whether site is responding")
    status_code: int | None = Field(default=None, description="HTTP status code")
    response_time_ms: float | None = gauge_field(
        "Response time in milliseconds", default=None, ge=0.0
    )
    last_check: float = Field(default=0.0, description="Unix timestamp of last check")
    error_message: str | None = Field(default=None, description="Error message if failed")


class SiteMonitorData(MetricData):
    """Aggregated site monitoring data.

    Attributes:
        sites: List of monitored site statuses
        total_up: Number of sites that are up
        total_down: Number of sites that are down
    """

    sites: list[SiteStatus] = Field(default_factory=list, description="Monitored sites")
    
    @property
    def total_up(self) -> int:
        """Count of sites that are up."""
        return sum(1 for site in self.sites if site.is_up)
    
    @property
    def total_down(self) -> int:
        """Count of sites that are down."""
        return sum(1 for site in self.sites if not site.is_up)


class SiteMonitorCollector(DataCollector[SiteMonitorData]):
    """Collector for site monitoring data.
    
    Checks configured URLs and returns their status.
    """

    def __init__(self, urls: list[str] | None = None, timeout: float = 5.0) -> None:
        """Initialize the collector.
        
        Args:
            urls: List of URLs to monitor (defaults to google.com)
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.urls = urls or ["https://www.google.com"]
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=True)
        return self._client

    def collect(self) -> SiteMonitorData:
        """Collect site status data.
        
        Returns:
            SiteMonitorData with status for all configured sites
        """
        sites: list[SiteStatus] = []
        client = self._get_client()
        
        for url in self.urls:
            start_time = time.time()
            try:
                response = client.get(url)
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                sites.append(SiteStatus(
                    url=url,
                    is_up=response.status_code < 400,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    last_check=end_time,
                    error_message=None,
                ))
            except Exception as e:
                end_time = time.time()
                sites.append(SiteStatus(
                    url=url,
                    is_up=False,
                    status_code=None,
                    response_time_ms=None,
                    last_check=end_time,
                    error_message=str(e),
                ))
        
        return SiteMonitorData(sites=sites)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._client is not None:
            self._client.close()
            self._client = None


class SiteMonitorPane(PanePlugin):
    """Site Monitor pane plugin for uptop."""

    name = "site_monitor"
    title = "Site Monitor"
    description = "Monitor website uptime and response times"
    default_enabled = True
    default_position = 5
    refresh_interval = 30.0  # Check every 30 seconds

    def __init__(self, urls: list[str] | None = None) -> None:
        """Initialize the pane plugin.
        
        Args:
            urls: List of URLs to monitor
        """
        super().__init__()
        self.urls = urls or ["https://www.google.com"]

    def create_collector(self) -> DataCollector[SiteMonitorData]:
        """Create the data collector for this pane."""
        return SiteMonitorCollector(urls=self.urls)

    def create_widget(self, data: Any = None, mode: DisplayMode = DisplayMode.MINIMIZED) -> Widget:
        """Create the widget for this pane."""
        from uptop.tui.panes.site_monitor_widget import SiteMonitorWidget
        return SiteMonitorWidget(data=data, id=f"pane-{self.name}")

    def get_default_config(self) -> dict[str, Any]:
        """Get default configuration for this pane."""
        return {
            "urls": ["https://www.google.com"],
            "timeout": 5.0,
            "refresh_interval": 30.0,
        }
