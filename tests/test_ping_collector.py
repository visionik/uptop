"""Tests for ping collector."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uptop.collectors.ping_collector import PingCollector
from uptop.plugins.ping_config import (
    AutoDisableConfig,
    PingHostConfig,
    PingPluginConfig,
    PingThresholds,
    RetryDNSConfig,
)
from uptop.plugins.ping_models import PingData


@pytest.fixture
def basic_config():
    """Create a basic ping plugin configuration."""
    return PingPluginConfig(
        enabled=True,
        hosts=[
            PingHostConfig(host="example.com"),
            PingHostConfig(host="192.168.1.1"),
        ],
    )


@pytest.fixture
def collector(basic_config):
    """Create a ping collector with basic config."""
    return PingCollector(basic_config)


class TestPingCollectorInit:
    """Tests for PingCollector initialization."""

    def test_init_with_config(self, basic_config):
        """Test collector initialization."""
        collector = PingCollector(basic_config)
        assert collector.config == basic_config
        assert collector.name == "ping"
        assert collector.default_interval == 1.0
        assert len(collector._dns_cache) == 0
        assert len(collector._history) == 0
        assert len(collector._consecutive_failures) == 0
        assert len(collector._disabled_hosts) == 0

    def test_history_buffer_size(self):
        """Test history buffer respects config size."""
        config = PingPluginConfig(
            hosts=[PingHostConfig(host="example.com")],
            history_size=100,
        )
        collector = PingCollector(config)
        # Add more than history_size entries
        for i in range(150):
            collector._history["example.com"].append(
                MagicMock(latency_ms=float(i), success=True, timestamp=float(i))
            )
        # Should only keep last 100
        assert len(collector._history["example.com"]) == 100


class TestPingCommand:
    """Tests for ping command generation."""

    @patch("platform.system")
    def test_macos_ping_command(self, mock_system, collector):
        """Test macOS ping command generation."""
        mock_system.return_value = "Darwin"
        collector._os_type = "darwin"
        
        cmd = collector._get_ping_command("example.com", 3, 2.0)
        assert cmd == ["/sbin/ping", "-c", "3", "-W", "2000", "example.com"]

    @patch("platform.system")
    def test_linux_ping_command(self, mock_system, collector):
        """Test Linux ping command generation."""
        mock_system.return_value = "Linux"
        collector._os_type = "linux"
        
        cmd = collector._get_ping_command("example.com", 3, 2.0)
        assert cmd == ["/bin/ping", "-c", "3", "-W", "2", "example.com"]


class TestDNSResolution:
    """Tests for DNS resolution."""

    @pytest.mark.asyncio
    async def test_resolve_hostname_success(self, collector):
        """Test successful DNS resolution."""
        host_config = PingHostConfig(host="example.com")
        
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            ip = await collector._resolve_hostname("example.com", host_config)
            assert ip == "93.184.216.34"
            assert collector._dns_cache["example.com"] == "93.184.216.34"

    @pytest.mark.asyncio
    async def test_resolve_uses_cache(self, collector):
        """Test that DNS resolution uses cache."""
        collector._dns_cache["example.com"] = "93.184.216.34"
        host_config = PingHostConfig(host="example.com")
        
        # Should not call gethostbyname
        with patch("socket.gethostbyname") as mock_resolve:
            ip = await collector._resolve_hostname("example.com", host_config)
            assert ip == "93.184.216.34"
            mock_resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_hostname_failure(self, collector):
        """Test DNS resolution failure."""
        import socket
        host_config = PingHostConfig(host="nonexistent.invalid")
        
        with patch("socket.gethostbyname", side_effect=socket.gaierror("Name resolution failed")):
            ip = await collector._resolve_hostname("nonexistent.invalid", host_config)
            assert ip is None

    @pytest.mark.asyncio
    async def test_resolve_with_retry(self):
        """Test DNS resolution retry logic."""
        config = PingPluginConfig(
            hosts=[PingHostConfig(host="example.com")],
            retry_dns=RetryDNSConfig(
                enabled=True,
                max_attempts=3,
                backoff_seconds=[0.1, 0.2],
            ),
        )
        collector = PingCollector(config)
        host_config = PingHostConfig(host="example.com")
        
        import socket
        attempts = []
        
        def mock_resolve(host):
            attempts.append(1)
            if len(attempts) < 2:
                raise socket.gaierror("Temporary failure")
            return "93.184.216.34"
        
        with patch("socket.gethostbyname", side_effect=mock_resolve):
            ip = await collector._resolve_hostname("example.com", host_config)
            assert ip == "93.184.216.34"
            assert len(attempts) == 2


class TestPingParsing:
    """Tests for ping output parsing."""

    def test_parse_successful_pings_macos(self, collector):
        """Test parsing successful macOS ping output."""
        output = """PING example.com (93.184.216.34): 56 data bytes
64 bytes from 93.184.216.34: icmp_seq=0 ttl=56 time=42.5 ms
64 bytes from 93.184.216.34: icmp_seq=1 ttl=56 time=43.2 ms
64 bytes from 93.184.216.34: icmp_seq=2 ttl=56 time=41.8 ms

--- example.com ping statistics ---
3 packets transmitted, 3 received, 0.0% packet loss
round-trip min/avg/max/stddev = 41.8/42.5/43.2/0.6 ms"""
        
        latencies, packet_loss = collector._parse_ping_output(output, 3)
        assert len(latencies) == 3
        assert latencies == [42.5, 43.2, 41.8]
        assert packet_loss == 0.0

    def test_parse_successful_pings_linux(self, collector):
        """Test parsing successful Linux ping output."""
        output = """PING example.com (93.184.216.34) 56(84) bytes of data.
64 bytes from 93.184.216.34: icmp_seq=1 ttl=56 time=42.5 ms
64 bytes from 93.184.216.34: icmp_seq=2 ttl=56 time=43.2 ms
64 bytes from 93.184.216.34: icmp_seq=3 ttl=56 time=41.8 ms

--- example.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 41.8/42.5/43.2/0.6 ms"""
        
        latencies, packet_loss = collector._parse_ping_output(output, 3)
        assert len(latencies) == 3
        assert packet_loss == 0.0

    def test_parse_with_packet_loss(self, collector):
        """Test parsing output with packet loss."""
        output = """PING example.com (93.184.216.34): 56 data bytes
64 bytes from 93.184.216.34: icmp_seq=0 ttl=56 time=42.5 ms
Request timeout for icmp_seq 1

--- example.com ping statistics ---
3 packets transmitted, 1 received, 66.7% packet loss"""
        
        latencies, packet_loss = collector._parse_ping_output(output, 3)
        assert len(latencies) == 1
        assert latencies[0] == 42.5
        assert packet_loss == 66.7

    def test_parse_total_failure(self, collector):
        """Test parsing output with 100% packet loss."""
        output = """PING example.com (93.184.216.34): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1
Request timeout for icmp_seq 2

--- example.com ping statistics ---
3 packets transmitted, 0 received, 100.0% packet loss"""
        
        latencies, packet_loss = collector._parse_ping_output(output, 3)
        assert len(latencies) == 0
        assert packet_loss == 100.0

    def test_parse_empty_output(self, collector):
        """Test parsing empty output."""
        latencies, packet_loss = collector._parse_ping_output("", 3)
        assert len(latencies) == 0
        assert packet_loss == 100.0


class TestThresholdEvaluation:
    """Tests for threshold evaluation."""

    def test_evaluate_ok(self, collector):
        """Test OK status."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(50.0, 2.0, thresholds)
        assert level == "ok"

    def test_evaluate_warning_latency(self, collector):
        """Test warning due to latency."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(150.0, 2.0, thresholds)
        assert level == "warning"

    def test_evaluate_warning_packet_loss(self, collector):
        """Test warning due to packet loss."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(50.0, 10.0, thresholds)
        assert level == "warning"

    def test_evaluate_critical_latency(self, collector):
        """Test critical due to latency."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(600.0, 2.0, thresholds)
        assert level == "critical"

    def test_evaluate_critical_packet_loss(self, collector):
        """Test critical due to packet loss."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(50.0, 25.0, thresholds)
        assert level == "critical"

    def test_evaluate_critical_takes_precedence(self, collector):
        """Test critical takes precedence over warning."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(600.0, 25.0, thresholds)
        assert level == "critical"

    def test_evaluate_none_latency(self, collector):
        """Test evaluation with None latency (host down)."""
        thresholds = PingThresholds()
        level = collector._evaluate_thresholds(None, 100.0, thresholds)
        assert level == "critical"


class TestAutoDisable:
    """Tests for auto-disable functionality."""

    def test_auto_disable_after_threshold(self):
        """Test that host is disabled after threshold failures."""
        config = PingPluginConfig(
            hosts=[PingHostConfig(host="example.com")],
            auto_disable=AutoDisableConfig(
                enabled=True,
                consecutive_failures_threshold=3,
            ),
        )
        collector = PingCollector(config)
        
        # Simulate failures
        collector._consecutive_failures["example.com"] = 3
        collector._check_auto_disable("example.com")
        
        assert "example.com" in collector._disabled_hosts

    def test_auto_disable_disabled(self):
        """Test that auto-disable can be disabled."""
        config = PingPluginConfig(
            hosts=[PingHostConfig(host="example.com")],
            auto_disable=AutoDisableConfig(enabled=False),
        )
        collector = PingCollector(config)
        
        collector._consecutive_failures["example.com"] = 100
        collector._check_auto_disable("example.com")
        
        assert "example.com" not in collector._disabled_hosts


class TestHistoryManagement:
    """Tests for history buffer management."""

    def test_update_history(self, collector):
        """Test updating history buffer."""
        from uptop.plugins.ping_models import PingMetrics
        
        metric = PingMetrics(latency_ms=42.5, success=True, timestamp=1234567890.0)
        collector._update_history("example.com", metric)
        
        assert len(collector._history["example.com"]) == 1
        assert collector._history["example.com"][0] == metric

    def test_history_respects_max_size(self):
        """Test that history buffer respects max size."""
        from uptop.plugins.ping_models import PingMetrics
        
        config = PingPluginConfig(
            hosts=[PingHostConfig(host="example.com")],
            history_size=5,
        )
        collector = PingCollector(config)
        
        # Add 10 metrics
        for i in range(10):
            metric = PingMetrics(
                latency_ms=float(i),
                success=True,
                timestamp=float(i),
            )
            collector._update_history("example.com", metric)
        
        # Should only keep last 5
        assert len(collector._history["example.com"]) == 5
        # Should keep the most recent ones (5-9)
        assert collector._history["example.com"][0].latency_ms == 5.0
        assert collector._history["example.com"][-1].latency_ms == 9.0


class TestPingHostIntegration:
    """Integration tests for pinging a single host."""

    @pytest.mark.asyncio
    async def test_ping_host_success(self, collector):
        """Test successful ping of a host."""
        host_config = PingHostConfig(host="example.com")
        
        ping_output = """PING example.com (93.184.216.34): 56 data bytes
64 bytes from 93.184.216.34: icmp_seq=0 ttl=56 time=42.5 ms
64 bytes from 93.184.216.34: icmp_seq=1 ttl=56 time=43.2 ms
64 bytes from 93.184.216.34: icmp_seq=2 ttl=56 time=41.8 ms

--- example.com ping statistics ---
3 packets transmitted, 3 received, 0.0% packet loss"""
        
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            with patch.object(
                collector, "_execute_ping", return_value=(ping_output, "", 0)
            ):
                result = await collector._ping_host(host_config)
        
        assert result.host == "example.com"
        assert result.ip_address == "93.184.216.34"
        assert result.status == "up"
        assert result.current_latency_ms == 41.8
        assert result.min_latency_ms == 41.8
        assert result.max_latency_ms == 43.2
        assert result.packet_loss_percent == 0.0
        assert result.consecutive_failures == 0
        assert result.alert_level == "ok"

    @pytest.mark.asyncio
    async def test_ping_host_dns_failure(self, collector):
        """Test ping with DNS failure."""
        import socket
        host_config = PingHostConfig(host="nonexistent.invalid")
        
        with patch("socket.gethostbyname", side_effect=socket.gaierror("DNS failed")):
            result = await collector._ping_host(host_config)
        
        assert result.host == "nonexistent.invalid"
        assert result.ip_address is None
        assert result.status == "dns_failed"
        assert result.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_ping_host_down(self, collector):
        """Test ping of down host."""
        host_config = PingHostConfig(host="example.com")
        
        ping_output = """PING example.com (93.184.216.34): 56 data bytes
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1
Request timeout for icmp_seq 2

--- example.com ping statistics ---
3 packets transmitted, 0 received, 100.0% packet loss"""
        
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            with patch.object(
                collector, "_execute_ping", return_value=(ping_output, "", 1)
            ):
                result = await collector._ping_host(host_config)
        
        assert result.status == "down"
        assert result.current_latency_ms is None
        assert result.packet_loss_percent == 100.0
        assert result.consecutive_failures == 1


class TestCollect:
    """Tests for main collect method."""

    @pytest.mark.asyncio
    async def test_collect_empty_hosts(self):
        """Test collect with no configured hosts."""
        config = PingPluginConfig(hosts=[])
        collector = PingCollector(config)
        
        data = await collector.collect()
        
        assert isinstance(data, PingData)
        assert len(data.hosts) == 0
        assert data.total_hosts == 0
        assert data.hosts_up == 0
        assert data.hosts_down == 0

    @pytest.mark.asyncio
    async def test_collect_multiple_hosts(self):
        """Test collect with multiple hosts."""
        config = PingPluginConfig(
            hosts=[
                PingHostConfig(host="example.com"),
                PingHostConfig(host="example.org"),
            ],
            concurrent_limit=10,
        )
        collector = PingCollector(config)
        
        # Mock successful ping
        from uptop.plugins.ping_models import HostPingResult
        import time
        
        mock_result = HostPingResult(
            host="example.com",
            ip_address="93.184.216.34",
            status="up",
            current_latency_ms=42.5,
            last_updated=time.time(),
        )
        
        with patch.object(collector, "_ping_host", return_value=mock_result):
            data = await collector.collect()
        
        assert isinstance(data, PingData)
        assert data.total_hosts == 2
        assert len(data.hosts) == 2

    @pytest.mark.asyncio
    async def test_collect_respects_concurrent_limit(self):
        """Test that collect respects concurrent limit."""
        config = PingPluginConfig(
            hosts=[PingHostConfig(host=f"host{i}.example.com") for i in range(20)],
            concurrent_limit=5,
        )
        collector = PingCollector(config)
        
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        
        async def mock_ping(host_config):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1
            
            from uptop.plugins.ping_models import HostPingResult
            import time
            return HostPingResult(
                host=host_config.host,
                status="up",
                last_updated=time.time(),
            )
        
        with patch.object(collector, "_ping_host", side_effect=mock_ping):
            await collector.collect()
        
        assert max_concurrent <= 5
