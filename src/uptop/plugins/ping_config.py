"""Configuration models for ping monitoring plugin.

This module defines Pydantic models for ping plugin configuration including:
- PingThresholds: Alert threshold configuration
- RetryDNSConfig: DNS retry policy configuration
- AutoDisableConfig: Auto-disable configuration
- PingHostConfig: Per-host configuration
- PingPluginConfig: Top-level plugin configuration
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PingThresholds(BaseModel):
    """Alert threshold configuration for ping monitoring.

    Attributes:
        warning_latency_ms: Latency threshold for warning alert (milliseconds)
        critical_latency_ms: Latency threshold for critical alert (milliseconds)
        warning_packet_loss_percent: Packet loss threshold for warning (0-100)
        critical_packet_loss_percent: Packet loss threshold for critical (0-100)
    """

    warning_latency_ms: float = Field(
        default=100.0, ge=0.0, description="Warning latency threshold in ms"
    )
    critical_latency_ms: float = Field(
        default=500.0, ge=0.0, description="Critical latency threshold in ms"
    )
    warning_packet_loss_percent: float = Field(
        default=5.0, ge=0.0, le=100.0, description="Warning packet loss threshold"
    )
    critical_packet_loss_percent: float = Field(
        default=20.0, ge=0.0, le=100.0, description="Critical packet loss threshold"
    )

    @field_validator("critical_latency_ms")
    @classmethod
    def validate_critical_greater_than_warning(
        cls, v: float, info: dict
    ) -> float:
        """Ensure critical threshold is greater than warning threshold."""
        if "warning_latency_ms" in info.data:
            warning = info.data["warning_latency_ms"]
            if v <= warning:
                raise ValueError(
                    f"critical_latency_ms ({v}) must be greater than "
                    f"warning_latency_ms ({warning})"
                )
        return v

    @field_validator("critical_packet_loss_percent")
    @classmethod
    def validate_critical_packet_loss(cls, v: float, info: dict) -> float:
        """Ensure critical packet loss is greater than warning."""
        if "warning_packet_loss_percent" in info.data:
            warning = info.data["warning_packet_loss_percent"]
            if v <= warning:
                raise ValueError(
                    f"critical_packet_loss_percent ({v}) must be greater than "
                    f"warning_packet_loss_percent ({warning})"
                )
        return v


class RetryDNSConfig(BaseModel):
    """DNS retry policy configuration.

    Attributes:
        enabled: Whether to retry DNS resolution on failure
        max_attempts: Maximum number of retry attempts
        backoff_seconds: List of backoff delays between retries
    """

    enabled: bool = Field(default=True, description="Enable DNS retry")
    max_attempts: int = Field(default=3, ge=1, le=10, description="Max retry attempts")
    backoff_seconds: list[float] = Field(
        default=[1.0, 2.0, 4.0], description="Backoff delays in seconds"
    )

    @field_validator("backoff_seconds")
    @classmethod
    def validate_backoff_list(cls, v: list[float]) -> list[float]:
        """Ensure backoff list has at least one entry and all values are positive."""
        if not v:
            raise ValueError("backoff_seconds must have at least one entry")
        if any(delay < 0 for delay in v):
            raise ValueError("All backoff delays must be non-negative")
        return v


class AutoDisableConfig(BaseModel):
    """Auto-disable configuration for failing hosts.

    Attributes:
        enabled: Whether to auto-disable hosts after consecutive failures
        consecutive_failures_threshold: Number of failures before disabling
    """

    enabled: bool = Field(default=True, description="Enable auto-disable")
    consecutive_failures_threshold: int = Field(
        default=10, ge=1, description="Failures before auto-disable"
    )


class PingHostConfig(BaseModel):
    """Per-host ping configuration.

    Attributes:
        host: Hostname or IP address to ping
        interval: Override default ping interval (seconds)
        timeout: Override default ping timeout (seconds)
        thresholds: Override default alert thresholds
    """

    host: str = Field(..., min_length=1, description="Hostname or IP address")
    interval: float | None = Field(
        default=None, ge=0.1, description="Ping interval in seconds"
    )
    timeout: float | None = Field(
        default=None, ge=0.5, description="Ping timeout in seconds"
    )
    thresholds: PingThresholds | None = Field(
        default=None, description="Per-host threshold overrides"
    )


class PingPluginConfig(BaseModel):
    """Top-level ping plugin configuration.

    Attributes:
        enabled: Whether the ping plugin is enabled
        default_interval: Default ping interval in seconds
        default_timeout: Default ping timeout in seconds
        concurrent_limit: Maximum concurrent ping operations
        pings_per_check: Number of pings to send per check
        history_size: Maximum history buffer size per host
        default_thresholds: Default alert thresholds
        retry_dns: DNS retry configuration
        auto_disable: Auto-disable configuration
        hosts: List of hosts to monitor
    """

    enabled: bool = Field(default=True, description="Enable ping plugin")
    default_interval: float = Field(
        default=1.0, ge=0.1, le=3600.0, description="Default ping interval in seconds"
    )
    default_timeout: float = Field(
        default=2.0, ge=0.5, description="Default ping timeout in seconds"
    )
    concurrent_limit: int = Field(
        default=10, ge=1, le=100, description="Max concurrent ping operations"
    )
    pings_per_check: int = Field(
        default=3, ge=1, le=10, description="Number of pings per check"
    )
    history_size: int = Field(
        default=300, ge=10, le=10000, description="History buffer size per host"
    )
    default_thresholds: PingThresholds = Field(
        default_factory=PingThresholds, description="Default alert thresholds"
    )
    retry_dns: RetryDNSConfig = Field(
        default_factory=RetryDNSConfig, description="DNS retry configuration"
    )
    auto_disable: AutoDisableConfig = Field(
        default_factory=AutoDisableConfig, description="Auto-disable configuration"
    )
    hosts: list[PingHostConfig] = Field(
        default_factory=list, description="List of hosts to monitor"
    )

    @field_validator("hosts")
    @classmethod
    def validate_unique_hosts(cls, v: list[PingHostConfig]) -> list[PingHostConfig]:
        """Ensure host names are unique."""
        hosts_seen = set()
        for host_config in v:
            if host_config.host in hosts_seen:
                raise ValueError(f"Duplicate host: {host_config.host}")
            hosts_seen.add(host_config.host)
        return v
