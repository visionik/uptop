"""Tests for ping monitoring configuration models."""

import pytest
from pydantic import ValidationError

from uptop.plugins.ping_config import (
    AutoDisableConfig,
    PingHostConfig,
    PingPluginConfig,
    PingThresholds,
    RetryDNSConfig,
)


class TestPingThresholds:
    """Tests for PingThresholds model."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = PingThresholds()
        assert thresholds.warning_latency_ms == 100.0
        assert thresholds.critical_latency_ms == 500.0
        assert thresholds.warning_packet_loss_percent == 5.0
        assert thresholds.critical_packet_loss_percent == 20.0

    def test_custom_thresholds(self):
        """Test custom threshold values."""
        thresholds = PingThresholds(
            warning_latency_ms=50.0,
            critical_latency_ms=200.0,
            warning_packet_loss_percent=10.0,
            critical_packet_loss_percent=30.0,
        )
        assert thresholds.warning_latency_ms == 50.0
        assert thresholds.critical_latency_ms == 200.0

    def test_critical_must_be_greater_than_warning_latency(self):
        """Test that critical latency must be > warning latency."""
        with pytest.raises(ValidationError) as exc_info:
            PingThresholds(
                warning_latency_ms=500.0,
                critical_latency_ms=100.0,  # Less than warning
            )
        assert "must be greater than" in str(exc_info.value)

    def test_critical_equal_to_warning_latency_rejected(self):
        """Test that critical == warning is also rejected."""
        with pytest.raises(ValidationError):
            PingThresholds(
                warning_latency_ms=100.0,
                critical_latency_ms=100.0,  # Equal to warning
            )

    def test_critical_must_be_greater_than_warning_packet_loss(self):
        """Test that critical packet loss must be > warning."""
        with pytest.raises(ValidationError) as exc_info:
            PingThresholds(
                warning_packet_loss_percent=20.0,
                critical_packet_loss_percent=10.0,  # Less than warning
            )
        assert "must be greater than" in str(exc_info.value)

    def test_negative_thresholds_rejected(self):
        """Test that negative thresholds are rejected."""
        with pytest.raises(ValidationError):
            PingThresholds(warning_latency_ms=-1.0)

        with pytest.raises(ValidationError):
            PingThresholds(critical_latency_ms=-1.0)

    def test_packet_loss_over_100_rejected(self):
        """Test that packet loss > 100% is rejected."""
        with pytest.raises(ValidationError):
            PingThresholds(warning_packet_loss_percent=101.0)

        with pytest.raises(ValidationError):
            PingThresholds(critical_packet_loss_percent=101.0)


class TestRetryDNSConfig:
    """Tests for RetryDNSConfig model."""

    def test_default_retry_config(self):
        """Test default retry configuration."""
        config = RetryDNSConfig()
        assert config.enabled is True
        assert config.max_attempts == 3
        assert config.backoff_seconds == [1.0, 2.0, 4.0]

    def test_custom_retry_config(self):
        """Test custom retry configuration."""
        config = RetryDNSConfig(
            enabled=False,
            max_attempts=5,
            backoff_seconds=[2.0, 4.0, 8.0, 16.0],
        )
        assert config.enabled is False
        assert config.max_attempts == 5
        assert len(config.backoff_seconds) == 4

    def test_max_attempts_bounds(self):
        """Test max_attempts validation."""
        # Too low
        with pytest.raises(ValidationError):
            RetryDNSConfig(max_attempts=0)

        # Too high
        with pytest.raises(ValidationError):
            RetryDNSConfig(max_attempts=11)

    def test_empty_backoff_list_rejected(self):
        """Test that empty backoff list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RetryDNSConfig(backoff_seconds=[])
        assert "at least one entry" in str(exc_info.value)

    def test_negative_backoff_rejected(self):
        """Test that negative backoff values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RetryDNSConfig(backoff_seconds=[1.0, -2.0, 4.0])
        assert "non-negative" in str(exc_info.value)


class TestAutoDisableConfig:
    """Tests for AutoDisableConfig model."""

    def test_default_auto_disable(self):
        """Test default auto-disable configuration."""
        config = AutoDisableConfig()
        assert config.enabled is True
        assert config.consecutive_failures_threshold == 10

    def test_custom_auto_disable(self):
        """Test custom auto-disable configuration."""
        config = AutoDisableConfig(
            enabled=False,
            consecutive_failures_threshold=5,
        )
        assert config.enabled is False
        assert config.consecutive_failures_threshold == 5

    def test_threshold_must_be_positive(self):
        """Test that threshold must be >= 1."""
        with pytest.raises(ValidationError):
            AutoDisableConfig(consecutive_failures_threshold=0)


class TestPingHostConfig:
    """Tests for PingHostConfig model."""

    def test_minimal_host_config(self):
        """Test minimal host configuration."""
        config = PingHostConfig(host="example.com")
        assert config.host == "example.com"
        assert config.interval is None
        assert config.timeout is None
        assert config.thresholds is None

    def test_full_host_config(self):
        """Test full host configuration with overrides."""
        thresholds = PingThresholds(
            warning_latency_ms=50.0,
            critical_latency_ms=200.0,
        )
        config = PingHostConfig(
            host="192.168.1.1",
            interval=2.0,
            timeout=3.0,
            thresholds=thresholds,
        )
        assert config.host == "192.168.1.1"
        assert config.interval == 2.0
        assert config.timeout == 3.0
        assert config.thresholds is not None
        assert config.thresholds.warning_latency_ms == 50.0

    def test_empty_host_rejected(self):
        """Test that empty host string is rejected."""
        with pytest.raises(ValidationError):
            PingHostConfig(host="")

    def test_interval_bounds(self):
        """Test interval validation."""
        # Too low
        with pytest.raises(ValidationError):
            PingHostConfig(host="example.com", interval=0.05)

    def test_timeout_bounds(self):
        """Test timeout validation."""
        # Too low
        with pytest.raises(ValidationError):
            PingHostConfig(host="example.com", timeout=0.1)


class TestPingPluginConfig:
    """Tests for PingPluginConfig model."""

    def test_default_plugin_config(self):
        """Test default plugin configuration."""
        config = PingPluginConfig()
        assert config.enabled is True
        assert config.default_interval == 1.0
        assert config.default_timeout == 2.0
        assert config.concurrent_limit == 10
        assert config.pings_per_check == 3
        assert config.history_size == 300
        assert len(config.hosts) == 0

    def test_custom_plugin_config(self):
        """Test custom plugin configuration."""
        hosts = [
            PingHostConfig(host="example.com"),
            PingHostConfig(host="example.org", interval=2.0),
        ]
        thresholds = PingThresholds(
            warning_latency_ms=150.0,
            critical_latency_ms=600.0,
        )
        config = PingPluginConfig(
            enabled=False,
            default_interval=2.0,
            default_timeout=3.0,
            concurrent_limit=5,
            pings_per_check=5,
            history_size=500,
            default_thresholds=thresholds,
            hosts=hosts,
        )
        assert config.enabled is False
        assert config.default_interval == 2.0
        assert config.concurrent_limit == 5
        assert len(config.hosts) == 2

    def test_interval_bounds(self):
        """Test interval bounds validation."""
        # Too low
        with pytest.raises(ValidationError):
            PingPluginConfig(default_interval=0.05)

        # Too high
        with pytest.raises(ValidationError):
            PingPluginConfig(default_interval=4000.0)

    def test_concurrent_limit_bounds(self):
        """Test concurrent limit bounds."""
        # Too low
        with pytest.raises(ValidationError):
            PingPluginConfig(concurrent_limit=0)

        # Too high
        with pytest.raises(ValidationError):
            PingPluginConfig(concurrent_limit=101)

    def test_pings_per_check_bounds(self):
        """Test pings per check bounds."""
        # Too low
        with pytest.raises(ValidationError):
            PingPluginConfig(pings_per_check=0)

        # Too high
        with pytest.raises(ValidationError):
            PingPluginConfig(pings_per_check=11)

    def test_history_size_bounds(self):
        """Test history size bounds."""
        # Too low
        with pytest.raises(ValidationError):
            PingPluginConfig(history_size=5)

        # Too high
        with pytest.raises(ValidationError):
            PingPluginConfig(history_size=20000)

    def test_duplicate_hosts_rejected(self):
        """Test that duplicate host names are rejected."""
        hosts = [
            PingHostConfig(host="example.com"),
            PingHostConfig(host="example.com"),  # Duplicate
        ]
        with pytest.raises(ValidationError) as exc_info:
            PingPluginConfig(hosts=hosts)
        assert "Duplicate host" in str(exc_info.value)

    def test_unique_hosts_accepted(self):
        """Test that unique host names are accepted."""
        hosts = [
            PingHostConfig(host="example.com"),
            PingHostConfig(host="example.org"),
            PingHostConfig(host="192.168.1.1"),
        ]
        config = PingPluginConfig(hosts=hosts)
        assert len(config.hosts) == 3
