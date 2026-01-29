"""Tests for ping monitoring data models."""

import time

import pytest
from pydantic import ValidationError

from uptop.plugins.ping_models import HostPingResult, PingData, PingMetrics


class TestPingMetrics:
    """Tests for PingMetrics model."""

    def test_valid_ping_metric(self):
        """Test creating a valid ping metric."""
        timestamp = time.time()
        metric = PingMetrics(
            latency_ms=42.5,
            success=True,
            timestamp=timestamp,
        )
        assert metric.latency_ms == 42.5
        assert metric.success is True
        assert metric.timestamp == timestamp

    def test_failed_ping_metric(self):
        """Test creating a failed ping metric."""
        timestamp = time.time()
        metric = PingMetrics(
            latency_ms=None,
            success=False,
            timestamp=timestamp,
        )
        assert metric.latency_ms is None
        assert metric.success is False

    def test_negative_latency_rejected(self):
        """Test that negative latency is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PingMetrics(
                latency_ms=-5.0,
                success=True,
                timestamp=time.time(),
            )
        errors = exc_info.value.errors()
        assert any("greater_than_equal" in str(e["type"]) for e in errors)

    def test_ping_metrics_immutable(self):
        """Test that PingMetrics is frozen/immutable."""
        metric = PingMetrics(
            latency_ms=10.0,
            success=True,
            timestamp=time.time(),
        )
        with pytest.raises((ValidationError, AttributeError)):
            metric.latency_ms = 20.0  # type: ignore


class TestHostPingResult:
    """Tests for HostPingResult model."""

    def test_minimal_host_result(self):
        """Test creating a minimal host result."""
        timestamp = time.time()
        result = HostPingResult(
            host="example.com",
            status="up",
            last_updated=timestamp,
        )
        assert result.host == "example.com"
        assert result.status == "up"
        assert result.last_updated == timestamp
        assert result.alert_level == "ok"
        assert result.packet_loss_percent == 0.0
        assert result.consecutive_failures == 0
        assert len(result.history) == 0

    def test_full_host_result(self):
        """Test creating a complete host result."""
        timestamp = time.time()
        history = [
            PingMetrics(latency_ms=10.0, success=True, timestamp=timestamp - 2),
            PingMetrics(latency_ms=12.0, success=True, timestamp=timestamp - 1),
            PingMetrics(latency_ms=11.0, success=True, timestamp=timestamp),
        ]
        result = HostPingResult(
            host="192.168.1.1",
            ip_address="192.168.1.1",
            status="up",
            current_latency_ms=11.0,
            min_latency_ms=10.0,
            avg_latency_ms=11.0,
            max_latency_ms=12.0,
            jitter_ms=0.8,
            packet_loss_percent=0.0,
            consecutive_failures=0,
            alert_level="ok",
            history=history,
            last_updated=timestamp,
        )
        assert result.current_latency_ms == 11.0
        assert result.min_latency_ms == 10.0
        assert result.avg_latency_ms == 11.0
        assert result.max_latency_ms == 12.0
        assert result.jitter_ms == 0.8
        assert len(result.history) == 3

    def test_dns_failed_status(self):
        """Test host with DNS failure."""
        result = HostPingResult(
            host="nonexistent.example.com",
            ip_address=None,
            status="dns_failed",
            last_updated=time.time(),
        )
        assert result.status == "dns_failed"
        assert result.ip_address is None

    def test_warning_alert_level(self):
        """Test host with warning alert level."""
        result = HostPingResult(
            host="example.com",
            status="up",
            current_latency_ms=150.0,
            alert_level="warning",
            last_updated=time.time(),
        )
        assert result.alert_level == "warning"

    def test_critical_alert_level(self):
        """Test host with critical alert level."""
        result = HostPingResult(
            host="example.com",
            status="up",
            current_latency_ms=600.0,
            packet_loss_percent=25.0,
            alert_level="critical",
            last_updated=time.time(),
        )
        assert result.alert_level == "critical"
        assert result.packet_loss_percent == 25.0

    def test_consecutive_failures(self):
        """Test tracking consecutive failures."""
        result = HostPingResult(
            host="example.com",
            status="down",
            consecutive_failures=5,
            last_updated=time.time(),
        )
        assert result.consecutive_failures == 5

    def test_packet_loss_bounds(self):
        """Test packet loss percentage bounds."""
        # Valid: 0%
        result = HostPingResult(
            host="example.com",
            status="up",
            packet_loss_percent=0.0,
            last_updated=time.time(),
        )
        assert result.packet_loss_percent == 0.0

        # Valid: 100%
        result = HostPingResult(
            host="example.com",
            status="down",
            packet_loss_percent=100.0,
            last_updated=time.time(),
        )
        assert result.packet_loss_percent == 100.0

        # Invalid: > 100%
        with pytest.raises(ValidationError):
            HostPingResult(
                host="example.com",
                status="down",
                packet_loss_percent=101.0,
                last_updated=time.time(),
            )

        # Invalid: < 0%
        with pytest.raises(ValidationError):
            HostPingResult(
                host="example.com",
                status="up",
                packet_loss_percent=-1.0,
                last_updated=time.time(),
            )


class TestPingData:
    """Tests for PingData model."""

    def test_empty_ping_data(self):
        """Test creating empty ping data."""
        data = PingData()
        assert len(data.hosts) == 0
        assert data.total_hosts == 0
        assert data.hosts_up == 0
        assert data.hosts_down == 0

    def test_ping_data_with_hosts(self):
        """Test creating ping data with multiple hosts."""
        timestamp = time.time()
        hosts = [
            HostPingResult(
                host="example.com",
                status="up",
                current_latency_ms=10.0,
                last_updated=timestamp,
            ),
            HostPingResult(
                host="example.org",
                status="up",
                current_latency_ms=15.0,
                last_updated=timestamp,
            ),
            HostPingResult(
                host="down.example.com",
                status="down",
                last_updated=timestamp,
            ),
        ]
        data = PingData(
            hosts=hosts,
            total_hosts=3,
            hosts_up=2,
            hosts_down=1,
        )
        assert len(data.hosts) == 3
        assert data.total_hosts == 3
        assert data.hosts_up == 2
        assert data.hosts_down == 1

    def test_ping_data_counters_validation(self):
        """Test that counters must be non-negative."""
        # Valid: all zeros
        data = PingData(
            total_hosts=0,
            hosts_up=0,
            hosts_down=0,
        )
        assert data.total_hosts == 0

        # Invalid: negative values
        with pytest.raises(ValidationError):
            PingData(total_hosts=-1)

        with pytest.raises(ValidationError):
            PingData(hosts_up=-1)

        with pytest.raises(ValidationError):
            PingData(hosts_down=-1)
