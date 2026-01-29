"""Data models for ping monitoring plugin.

This module defines Pydantic models for ping monitoring data including:
- PingMetrics: Single ping measurement
- HostPingResult: Aggregated ping results for a single host
- PingData: Complete ping monitoring data for all hosts
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from uptop.models.base import MetricData, counter_field, gauge_field


class PingMetrics(BaseModel):
    """Single ping measurement.

    Attributes:
        latency_ms: Latency in milliseconds (None if ping failed)
        success: Whether the ping succeeded
        timestamp: Unix timestamp of measurement
    """

    model_config = ConfigDict(frozen=True)

    latency_ms: float | None = gauge_field(
        "Latency in milliseconds", default=None, ge=0.0
    )
    success: bool = Field(..., description="Whether ping succeeded")
    timestamp: float = Field(..., description="Unix timestamp of measurement")


class HostPingResult(BaseModel):
    """Aggregated ping results for a single host.

    Contains current and historical ping statistics for a single monitored host.

    Attributes:
        host: Hostname or IP address
        ip_address: Resolved IP address (None if DNS failed)
        status: Current status (up|down|dns_failed|timeout)
        current_latency_ms: Most recent latency measurement
        min_latency_ms: Minimum latency observed
        avg_latency_ms: Average latency
        max_latency_ms: Maximum latency observed
        jitter_ms: Latency standard deviation (jitter)
        packet_loss_percent: Packet loss percentage (0-100)
        consecutive_failures: Number of consecutive failed pings
        alert_level: Alert level based on thresholds (ok|warning|critical)
        history: Recent ping history (limited by config)
        last_updated: Unix timestamp of last update
    """

    host: str = Field(..., description="Hostname or IP address")
    ip_address: str | None = Field(default=None, description="Resolved IP address")
    status: str = Field(..., description="up|down|dns_failed|timeout")
    current_latency_ms: float | None = gauge_field(
        "Current latency", default=None, ge=0.0
    )
    min_latency_ms: float | None = gauge_field(
        "Minimum latency", default=None, ge=0.0
    )
    avg_latency_ms: float | None = gauge_field(
        "Average latency", default=None, ge=0.0
    )
    max_latency_ms: float | None = gauge_field(
        "Maximum latency", default=None, ge=0.0
    )
    jitter_ms: float | None = gauge_field("Jitter (stddev)", default=None, ge=0.0)
    packet_loss_percent: float = gauge_field(
        "Packet loss percentage", default=0.0, ge=0.0, le=100.0
    )
    consecutive_failures: int = counter_field(
        "Consecutive failure count", default=0, ge=0
    )
    alert_level: str = Field(default="ok", description="ok|warning|critical")
    history: list[PingMetrics] = Field(
        default_factory=list, description="Recent ping history (max 300)"
    )
    last_updated: float = Field(..., description="Unix timestamp of last update")


class PingData(MetricData):
    """Complete ping monitoring data for all hosts.

    Top-level data model returned by the ping collector containing
    aggregated statistics for all monitored hosts.

    Attributes:
        hosts: Per-host ping results
        total_hosts: Total number of configured hosts
        hosts_up: Number of reachable hosts
        hosts_down: Number of unreachable hosts
    """

    hosts: list[HostPingResult] = Field(
        default_factory=list, description="Per-host ping results"
    )
    total_hosts: int = Field(default=0, ge=0, description="Total configured hosts")
    hosts_up: int = Field(default=0, ge=0, description="Number of reachable hosts")
    hosts_down: int = Field(default=0, ge=0, description="Number of unreachable hosts")
