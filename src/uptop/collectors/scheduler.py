"""Collection scheduler for managing async data collection tasks.

This module provides a scheduler that manages per-pane collection tasks
with configurable intervals, timeout handling, retry logic, and performance
monitoring.

Key features:
- Per-collector async tasks with configurable intervals
- Automatic retry with exponential backoff for transient failures
- Stale data detection for failed collections
- Independent failure handling (one pane's failure doesn't affect others)
"""

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from uptop.collectors.base import CollectionResult, DataCollector
from uptop.collectors.buffer import DataBuffer

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


@dataclass
class CollectorInfo:
    """Information about a registered collector.

    Attributes:
        collector: The DataCollector instance
        buffer: Buffer for storing collected data
        task: The asyncio task running collection loop (if started)
        last_result: Most recent collection result
        last_successful_result: Last result that succeeded (for stale data)
        total_timeouts: Count of collection timeouts
        retry_enabled: Whether to retry on transient failures
        max_retries: Maximum retry attempts per collection
        retry_base_delay: Base delay in seconds for retry backoff
        is_stale: Whether the data should be considered stale
        stale_threshold_multiplier: Mark stale after N intervals without success
    """

    collector: DataCollector[Any]
    buffer: DataBuffer[Any]
    task: asyncio.Task[None] | None = None
    last_result: CollectionResult[Any] | None = None
    last_successful_result: CollectionResult[Any] | None = None
    total_timeouts: int = 0
    retry_enabled: bool = True
    max_retries: int = 3
    retry_base_delay: float = 0.5
    is_stale: bool = False
    stale_threshold_multiplier: float = 3.0  # Mark stale after 3x interval


@dataclass
class SchedulerStats:
    """Statistics about the scheduler's state and performance.

    Attributes:
        running: Whether the scheduler is currently running
        collectors_registered: Number of registered collectors
        collectors_running: Number of actively running collectors
        total_collections: Sum of all collections across all collectors
        total_failures: Sum of all failures across all collectors
        total_timeouts: Sum of all timeouts across all collectors
        average_latency_ms: Average collection time in milliseconds
    """

    running: bool = False
    collectors_registered: int = 0
    collectors_running: int = 0
    total_collections: int = 0
    total_failures: int = 0
    total_timeouts: int = 0
    average_latency_ms: float = 0.0


# Type alias for collection callbacks
CollectionCallback = Callable[[str, CollectionResult[Any]], Coroutine[Any, Any, None]]


class CollectionScheduler:
    """Scheduler for managing async data collection tasks.

    Manages multiple collectors, each running in its own asyncio task
    at its configured interval. Provides timeout handling, performance
    monitoring, and graceful shutdown.

    Example:
        scheduler = CollectionScheduler()
        scheduler.register(cpu_collector, buffer_size=100)
        scheduler.register(memory_collector, buffer_size=100)

        await scheduler.start()
        # ... later ...
        await scheduler.stop()
    """

    def __init__(
        self,
        default_buffer_size: int = 1000,
        default_buffer_age: float | None = 300.0,
    ) -> None:
        """Initialize the scheduler.

        Args:
            default_buffer_size: Default max entries for collector buffers
            default_buffer_age: Default max age in seconds for buffer entries
        """
        self._collectors: dict[str, CollectorInfo] = {}
        self._running = False
        self._default_buffer_size = default_buffer_size
        self._default_buffer_age = default_buffer_age
        self._callbacks: list[CollectionCallback] = []

        # Latency tracking
        self._latencies: list[float] = []
        self._max_latency_samples = 1000

    @property
    def running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    def register(
        self,
        collector: DataCollector[Any],
        buffer_size: int | None = None,
        buffer_age: float | None = None,
        retry_enabled: bool = True,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
        stale_threshold_multiplier: float = 3.0,
    ) -> None:
        """Register a collector with the scheduler.

        Args:
            collector: The DataCollector to register
            buffer_size: Max buffer entries (uses default if not specified)
            buffer_age: Max age for buffer entries in seconds
            retry_enabled: Whether to retry on transient failures (default: True)
            max_retries: Maximum retry attempts per collection (default: 3)
            retry_base_delay: Base delay in seconds for retry backoff (default: 0.5)
            stale_threshold_multiplier: Mark data stale after N * interval
                without successful collection (default: 3.0)

        Raises:
            ValueError: If a collector with the same name is already registered
        """
        if collector.name in self._collectors:
            raise ValueError(f"Collector '{collector.name}' is already registered")

        size = buffer_size if buffer_size is not None else self._default_buffer_size
        age = buffer_age if buffer_age is not None else self._default_buffer_age

        buffer: DataBuffer[Any] = DataBuffer(max_size=size, max_age_seconds=age)

        self._collectors[collector.name] = CollectorInfo(
            collector=collector,
            buffer=buffer,
            retry_enabled=retry_enabled,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            stale_threshold_multiplier=stale_threshold_multiplier,
        )

    def unregister(self, name: str) -> None:
        """Unregister a collector.

        If the scheduler is running, the collector's task will be cancelled.

        Args:
            name: Name of the collector to unregister

        Raises:
            KeyError: If no collector with that name is registered
        """
        if name not in self._collectors:
            raise KeyError(f"Collector '{name}' is not registered")

        info = self._collectors[name]
        if info.task is not None and not info.task.done():
            info.task.cancel()

        del self._collectors[name]

    def get_collector(self, name: str) -> DataCollector[Any] | None:
        """Get a registered collector by name.

        Args:
            name: Name of the collector

        Returns:
            The DataCollector, or None if not found
        """
        info = self._collectors.get(name)
        return info.collector if info else None

    def get_buffer(self, name: str) -> DataBuffer[Any] | None:
        """Get a collector's buffer by name.

        Args:
            name: Name of the collector

        Returns:
            The DataBuffer, or None if not found
        """
        info = self._collectors.get(name)
        return info.buffer if info else None

    def get_latest(self, name: str) -> CollectionResult[Any] | None:
        """Get the most recent collection result for a collector.

        Args:
            name: Name of the collector

        Returns:
            The most recent CollectionResult, or None
        """
        info = self._collectors.get(name)
        return info.last_result if info else None

    def add_callback(self, callback: CollectionCallback) -> None:
        """Add a callback to be invoked after each collection.

        The callback receives the collector name and collection result.

        Args:
            callback: Async function(name, result) to call
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: CollectionCallback) -> None:
        """Remove a previously added callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def start(self) -> None:
        """Start all registered collectors.

        Creates an asyncio task for each collector that runs its
        collection loop at the configured interval.

        Does nothing if already running.
        """
        if self._running:
            return

        self._running = True

        for name, info in self._collectors.items():
            if info.collector.enabled:
                info.task = asyncio.create_task(
                    self._collection_loop(name),
                    name=f"collector-{name}",
                )

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop all collectors gracefully.

        Cancels all collection tasks and waits for them to finish.

        Args:
            timeout: Maximum seconds to wait for tasks to finish
        """
        if not self._running:
            return

        self._running = False

        # Cancel all tasks
        tasks: list[asyncio.Task[None]] = []
        for info in self._collectors.values():
            if info.task is not None and not info.task.done():
                info.task.cancel()
                tasks.append(info.task)

        # Wait for all tasks to finish
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)

        # Clear task references
        for info in self._collectors.values():
            info.task = None

    async def collect_once(self, name: str) -> CollectionResult[Any]:
        """Perform a single collection from a specific collector.

        Useful for on-demand collection outside the normal schedule.

        Args:
            name: Name of the collector

        Returns:
            The CollectionResult from this collection

        Raises:
            KeyError: If no collector with that name is registered
        """
        if name not in self._collectors:
            raise KeyError(f"Collector '{name}' is not registered")

        info = self._collectors[name]
        return await self._do_collection(info)

    async def collect_all_once(self) -> dict[str, CollectionResult[Any]]:
        """Perform a single collection from all registered collectors.

        Collects from all collectors in parallel.

        Returns:
            Dict mapping collector names to their results
        """
        tasks = {name: self._do_collection(info) for name, info in self._collectors.items()}

        results: dict[str, CollectionResult[Any]] = {}
        for name, coro in tasks.items():
            results[name] = await coro

        return results

    async def get_stats(self) -> SchedulerStats:
        """Get scheduler statistics.

        Returns:
            SchedulerStats with current state and performance info
        """
        total_collections = 0
        total_failures = 0
        total_timeouts = 0
        running_count = 0

        for info in self._collectors.values():
            stats = info.collector.stats
            total_collections += stats["total_collections"]
            total_failures += stats["total_failures"]
            total_timeouts += info.total_timeouts

            if info.task is not None and not info.task.done():
                running_count += 1

        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

        return SchedulerStats(
            running=self._running,
            collectors_registered=len(self._collectors),
            collectors_running=running_count,
            total_collections=total_collections,
            total_failures=total_failures,
            total_timeouts=total_timeouts,
            average_latency_ms=avg_latency,
        )

    async def _collection_loop(self, name: str) -> None:
        """Run the collection loop for a collector.

        This is the main loop that runs in each collector's task.
        It collects at the configured interval until stopped.

        Args:
            name: Name of the collector to run
        """
        info = self._collectors[name]

        while self._running and info.collector.enabled:
            await self._do_collection(info)

            # Sleep for the configured interval
            try:
                await asyncio.sleep(info.collector.interval)
            except asyncio.CancelledError:
                break

    async def _do_collection(
        self,
        info: CollectorInfo,
        use_retry: bool | None = None,
    ) -> CollectionResult[Any]:
        """Perform a single collection with timeout handling and optional retry.

        If retry is enabled and the collection fails with a non-permission error,
        the collection will be retried with exponential backoff.

        Args:
            info: CollectorInfo for the collector
            use_retry: Override retry setting (None uses info.retry_enabled)

        Returns:
            CollectionResult from this collection
        """
        should_retry = use_retry if use_retry is not None else info.retry_enabled

        try:
            if should_retry:
                # Use collect_with_retry for automatic retry with backoff
                result = await asyncio.wait_for(
                    info.collector.collect_with_retry(
                        max_retries=info.max_retries,
                        base_delay=info.retry_base_delay,
                    ),
                    timeout=info.collector.timeout * info.max_retries,
                )
            else:
                result = await asyncio.wait_for(
                    info.collector.safe_collect(),
                    timeout=info.collector.timeout,
                )
        except TimeoutError:
            info.total_timeouts += 1
            result = CollectionResult(
                success=False,
                error=f"Collection timed out after {info.collector.timeout}s",
                collector_name=info.collector.name,
            )
        except asyncio.CancelledError:
            # Re-raise cancellation
            raise

        # Store result
        info.last_result = result

        # Track latency
        self._latencies.append(result.collection_time_ms)
        if len(self._latencies) > self._max_latency_samples:
            self._latencies = self._latencies[-self._max_latency_samples :]

        # Handle success/failure for stale tracking
        if result.success and result.data is not None:
            # Store in buffer
            await info.buffer.add(result.data)

            # Mark as fresh and update last successful result
            info.last_successful_result = result
            if info.is_stale:
                logger.info(
                    "Collector '%s' recovered from stale state",
                    info.collector.name,
                )
                info.is_stale = False
        else:
            # Check if data should be marked as stale
            self._check_stale_state(info)

        # Invoke callbacks (even on failure, so UI can update)
        for callback in self._callbacks:
            with contextlib.suppress(Exception):
                await callback(info.collector.name, result)

        return result

    def _check_stale_state(self, info: CollectorInfo) -> None:
        """Check if collector data should be marked as stale.

        Data is considered stale if the last successful collection was more than
        stale_threshold_multiplier * interval seconds ago.

        Args:
            info: CollectorInfo to check
        """
        if info.last_successful_result is None:
            # Never had a successful collection - might be starting up
            return

        last_success_time = info.last_successful_result.timestamp
        threshold_seconds = info.collector.interval * info.stale_threshold_multiplier
        threshold_delta = timedelta(seconds=threshold_seconds)

        if _utcnow() - last_success_time > threshold_delta:
            if not info.is_stale:
                logger.warning(
                    "Collector '%s' data is now stale (last success: %s ago)",
                    info.collector.name,
                    _utcnow() - last_success_time,
                )
                info.is_stale = True

    def is_collector_stale(self, name: str) -> bool:
        """Check if a collector's data is stale.

        Args:
            name: Name of the collector

        Returns:
            True if the collector exists and its data is stale
        """
        info = self._collectors.get(name)
        return info.is_stale if info else False

    def get_last_successful_data(self, name: str) -> Any | None:
        """Get the last successfully collected data for a collector.

        Useful for displaying stale data with a stale indicator.

        Args:
            name: Name of the collector

        Returns:
            The data from the last successful collection, or None
        """
        info = self._collectors.get(name)
        if info and info.last_successful_result and info.last_successful_result.success:
            return info.last_successful_result.data
        return None

    def list_collectors(self) -> list[str]:
        """Get a list of all registered collector names.

        Returns:
            List of collector names
        """
        return list(self._collectors.keys())

    async def get_collector_stats(self, name: str) -> dict[str, Any] | None:
        """Get detailed statistics for a specific collector.

        Args:
            name: Name of the collector

        Returns:
            Dict with collector and buffer stats, or None if not found
        """
        info = self._collectors.get(name)
        if info is None:
            return None

        buffer_stats = await info.buffer.get_stats()

        # Calculate time since last successful collection
        last_success_ago = None
        if info.last_successful_result:
            last_success_ago = (
                _utcnow() - info.last_successful_result.timestamp
            ).total_seconds()

        return {
            "collector": info.collector.stats,
            "buffer": {
                "current_size": buffer_stats.current_size,
                "max_size": buffer_stats.max_size,
                "total_added": buffer_stats.total_added,
                "total_expired": buffer_stats.total_expired,
                "total_evicted": buffer_stats.total_evicted,
            },
            "timeouts": info.total_timeouts,
            "running": info.task is not None and not info.task.done(),
            "is_stale": info.is_stale,
            "retry_enabled": info.retry_enabled,
            "max_retries": info.max_retries,
            "last_success_seconds_ago": last_success_ago,
        }
