"""Ping collector for monitoring network latency and availability.

This module implements the PingCollector which:
- Resolves hostnames to IP addresses with retry logic
- Executes ping commands using system ping utility
- Parses ping output for latency and packet loss metrics
- Evaluates alert thresholds
- Maintains history buffers for sparkline visualization
- Handles errors gracefully with per-host isolation
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Sequence
import logging
import platform
import re
import socket
import statistics
import time
from typing import Any

from uptop.collectors.base import DataCollector
from uptop.plugins.ping_config import PingHostConfig, PingPluginConfig, PingThresholds
from uptop.plugins.ping_models import HostPingResult, PingData, PingMetrics

logger = logging.getLogger(__name__)


class PingCollector(DataCollector[PingData]):
    """Collector for ping monitoring metrics.

    Executes ping commands against configured hosts and collects latency,
    packet loss, and availability metrics.

    Attributes:
        name: Collector identifier
        default_interval: Default collection interval in seconds
        timeout: Maximum time allowed for collection
    """

    name: str = "ping"
    default_interval: float = 1.0
    timeout: float = 10.0

    def __init__(self, config: PingPluginConfig) -> None:
        """Initialize the ping collector.

        Args:
            config: Ping plugin configuration
        """
        super().__init__()
        self.config = config
        self._dns_cache: dict[str, str] = {}  # hostname -> IP
        self._history: dict[str, deque[PingMetrics]] = defaultdict(
            lambda: deque(maxlen=config.history_size)
        )
        self._consecutive_failures: dict[str, int] = defaultdict(int)
        self._disabled_hosts: set[str] = set()
        self._os_type = platform.system().lower()

    def _get_ping_command(
        self, host: str, count: int, timeout: float
    ) -> list[str]:
        """Get the platform-specific ping command.

        Args:
            host: Hostname or IP to ping
            count: Number of pings to send
            timeout: Timeout in seconds

        Returns:
            List of command arguments
        """
        if "darwin" in self._os_type:  # macOS
            return [
                "/sbin/ping",
                "-c",
                str(count),
                "-W",
                str(int(timeout * 1000)),  # macOS uses milliseconds
                host,
            ]
        else:  # Linux and others
            return [
                "/bin/ping",
                "-c",
                str(count),
                "-W",
                str(int(timeout)),  # Linux uses seconds
                host,
            ]

    async def _resolve_hostname(
        self, host: str, host_config: PingHostConfig
    ) -> str | None:
        """Resolve hostname to IP address with retry logic.

        Args:
            host: Hostname to resolve
            host_config: Host configuration

        Returns:
            IP address string, or None if resolution fails
        """
        # Check cache first
        if host in self._dns_cache:
            return self._dns_cache[host]

        # Try to resolve
        retry_config = self.config.retry_dns
        max_attempts = retry_config.max_attempts if retry_config.enabled else 1
        backoff_delays = retry_config.backoff_seconds

        for attempt in range(max_attempts):
            try:
                # Run blocking DNS lookup in thread pool
                loop = asyncio.get_event_loop()
                ip = await loop.run_in_executor(
                    None, socket.gethostbyname, host
                )
                self._dns_cache[host] = ip
                logger.debug(f"Resolved {host} to {ip}")
                return ip
            except socket.gaierror as e:
                if attempt < max_attempts - 1:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.debug(
                        f"DNS resolution failed for {host}, retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(f"DNS resolution failed for {host} after {max_attempts} attempts")
                    return None

        return None

    async def _execute_ping(
        self, host: str, count: int, timeout: float
    ) -> tuple[str, str, int]:
        """Execute ping command.

        Args:
            host: Host to ping
            count: Number of pings
            timeout: Timeout in seconds

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        cmd = self._get_ping_command(host, count, timeout)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout + 2.0
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                return stdout, stderr, process.returncode or 0
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return "", "Ping command timed out", 1

        except Exception as e:
            logger.error(f"Failed to execute ping command: {e}")
            return "", str(e), 1

    def _parse_ping_output(
        self, output: str, sent_count: int
    ) -> tuple[list[float], float]:
        """Parse ping command output.

        Args:
            output: Ping command stdout
            sent_count: Number of pings sent

        Returns:
            Tuple of (latencies, packet_loss_percent)
        """
        latencies: list[float] = []
        packets_received = 0

        # Parse individual ping lines for latencies
        # Pattern matches: "64 bytes from ... time=42.5 ms" (Linux/macOS)
        time_pattern = re.compile(r"time[=<]([0-9.]+)\s*ms", re.IGNORECASE)
        
        for line in output.split("\n"):
            match = time_pattern.search(line)
            if match:
                try:
                    latency = float(match.group(1))
                    latencies.append(latency)
                    packets_received += 1
                except ValueError:
                    continue

        # Calculate packet loss
        if sent_count > 0:
            packet_loss = ((sent_count - packets_received) / sent_count) * 100.0
        else:
            packet_loss = 100.0

        # Try to extract packet loss from statistics line as fallback
        # Pattern: "X packets transmitted, Y received, Z% packet loss"
        stats_pattern = re.compile(
            r"(\d+)\s+packets?\s+transmitted,\s+(\d+)\s+received,\s+([0-9.]+)%\s+packet\s+loss",
            re.IGNORECASE,
        )
        stats_match = stats_pattern.search(output)
        if stats_match:
            try:
                transmitted = int(stats_match.group(1))
                received = int(stats_match.group(2))
                loss_percent = float(stats_match.group(3))
                # Use statistics line packet loss if we didn't parse pings
                if not latencies:
                    packet_loss = loss_percent
                # Update packets received if more reliable
                if transmitted == sent_count:
                    packets_received = received
            except ValueError:
                pass

        return latencies, packet_loss

    def _evaluate_thresholds(
        self,
        current_latency: float | None,
        packet_loss: float,
        thresholds: PingThresholds,
    ) -> str:
        """Evaluate alert thresholds.

        Args:
            current_latency: Current latency in ms (None if down)
            packet_loss: Packet loss percentage
            thresholds: Threshold configuration

        Returns:
            Alert level: "ok", "warning", or "critical"
        """
        # Critical conditions
        if packet_loss >= thresholds.critical_packet_loss_percent:
            return "critical"
        if current_latency is not None and current_latency >= thresholds.critical_latency_ms:
            return "critical"

        # Warning conditions
        if packet_loss >= thresholds.warning_packet_loss_percent:
            return "warning"
        if current_latency is not None and current_latency >= thresholds.warning_latency_ms:
            return "warning"

        return "ok"

    def _update_history(self, host: str, metric: PingMetrics) -> None:
        """Update history buffer for a host.

        Args:
            host: Hostname
            metric: Ping metric to add
        """
        self._history[host].append(metric)

    async def _ping_host(
        self, host_config: PingHostConfig
    ) -> HostPingResult:
        """Ping a single host and collect metrics.

        Args:
            host_config: Host configuration

        Returns:
            HostPingResult with collected metrics
        """
        host = host_config.host
        timestamp = time.time()

        # Check if host is disabled
        if host in self._disabled_hosts:
            return HostPingResult(
                host=host,
                status="disabled",
                last_updated=timestamp,
                consecutive_failures=self._consecutive_failures[host],
            )

        # Resolve hostname
        ip_address = await self._resolve_hostname(host, host_config)
        if ip_address is None:
            self._consecutive_failures[host] += 1
            self._check_auto_disable(host)
            return HostPingResult(
                host=host,
                ip_address=None,
                status="dns_failed",
                last_updated=timestamp,
                consecutive_failures=self._consecutive_failures[host],
            )

        # Execute ping
        timeout = host_config.timeout or self.config.default_timeout
        count = self.config.pings_per_check
        
        stdout, stderr, exit_code = await self._execute_ping(
            ip_address, count, timeout
        )

        # Parse results
        latencies, packet_loss = self._parse_ping_output(stdout, count)

        # Determine status
        if not latencies and packet_loss >= 100.0:
            status = "down"
            current_latency = None
            min_lat = None
            avg_lat = None
            max_lat = None
            jitter = None
            self._consecutive_failures[host] += 1
        elif exit_code != 0 and not latencies:
            status = "timeout"
            current_latency = None
            min_lat = None
            avg_lat = None
            max_lat = None
            jitter = None
            self._consecutive_failures[host] += 1
        else:
            status = "up"
            current_latency = latencies[-1] if latencies else None
            min_lat = min(latencies) if latencies else None
            avg_lat = statistics.mean(latencies) if latencies else None
            max_lat = max(latencies) if latencies else None
            jitter = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
            self._consecutive_failures[host] = 0  # Reset on success

        # Update history
        if current_latency is not None:
            metric = PingMetrics(
                latency_ms=current_latency,
                success=True,
                timestamp=timestamp,
            )
        else:
            metric = PingMetrics(
                latency_ms=None,
                success=False,
                timestamp=timestamp,
            )
        self._update_history(host, metric)

        # Evaluate thresholds
        thresholds = host_config.thresholds or self.config.default_thresholds
        alert_level = self._evaluate_thresholds(current_latency, packet_loss, thresholds)

        # Check auto-disable
        self._check_auto_disable(host)

        return HostPingResult(
            host=host,
            ip_address=ip_address,
            status=status,
            current_latency_ms=current_latency,
            min_latency_ms=min_lat,
            avg_latency_ms=avg_lat,
            max_latency_ms=max_lat,
            jitter_ms=jitter,
            packet_loss_percent=packet_loss,
            consecutive_failures=self._consecutive_failures[host],
            alert_level=alert_level,
            history=list(self._history[host]),
            last_updated=timestamp,
        )

    def _check_auto_disable(self, host: str) -> None:
        """Check if host should be auto-disabled.

        Args:
            host: Hostname to check
        """
        auto_disable = self.config.auto_disable
        if not auto_disable.enabled:
            return

        threshold = auto_disable.consecutive_failures_threshold
        if self._consecutive_failures[host] >= threshold:
            self._disabled_hosts.add(host)
            logger.warning(
                f"Auto-disabled host {host} after {threshold} consecutive failures"
            )

    async def collect(self) -> PingData:
        """Collect ping metrics for all configured hosts.

        Returns:
            PingData with results for all hosts
        """
        if not self.config.hosts:
            return PingData(
                hosts=[],
                total_hosts=0,
                hosts_up=0,
                hosts_down=0,
            )

        # Create semaphore for concurrency limit
        semaphore = asyncio.Semaphore(self.config.concurrent_limit)

        async def ping_with_semaphore(host_config: PingHostConfig) -> HostPingResult:
            async with semaphore:
                return await self._ping_host(host_config)

        # Ping all hosts in parallel (with limit)
        tasks = [ping_with_semaphore(host_config) for host_config in self.config.hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        hosts: list[HostPingResult] = []
        hosts_up = 0
        hosts_down = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle unexpected errors
                host_config = self.config.hosts[i]
                logger.error(f"Unexpected error pinging {host_config.host}: {result}")
                hosts.append(
                    HostPingResult(
                        host=host_config.host,
                        status="error",
                        last_updated=time.time(),
                    )
                )
                hosts_down += 1
            else:
                hosts.append(result)
                if result.status == "up":
                    hosts_up += 1
                else:
                    hosts_down += 1

        return PingData(
            source=self.name,
            hosts=hosts,
            total_hosts=len(self.config.hosts),
            hosts_up=hosts_up,
            hosts_down=hosts_down,
        )

    def get_schema(self) -> type[PingData]:
        """Return the Pydantic model class for this collector's data.

        Returns:
            The PingData class
        """
        return PingData
