"""Tests for the data collection framework."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from uptop.collectors import (
    CollectionResult,
    CollectionScheduler,
    DataBuffer,
    DataCollector,
)
from uptop.models import MetricData


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


# Test fixtures and mock implementations


class MockMetricData(MetricData):
    """Mock metric data for testing."""

    value: float = 0.0


class MockCollector(DataCollector[MockMetricData]):
    """Mock collector for testing."""

    name = "mock_collector"
    default_interval = 0.1
    timeout = 1.0

    def __init__(self, value: float = 42.0) -> None:
        super().__init__()
        self.value = value
        self.collect_count = 0

    async def collect(self) -> MockMetricData:
        self.collect_count += 1
        return MockMetricData(value=self.value, source=self.name)

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


class FailingCollector(DataCollector[MockMetricData]):
    """Collector that always fails."""

    name = "failing_collector"
    default_interval = 0.1
    timeout = 1.0

    async def collect(self) -> MockMetricData:
        raise RuntimeError("Collection failed intentionally")

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


class SlowCollector(DataCollector[MockMetricData]):
    """Collector that takes too long."""

    name = "slow_collector"
    default_interval = 0.1
    timeout = 0.1  # Short timeout for testing

    async def collect(self) -> MockMetricData:
        await asyncio.sleep(1.0)  # Longer than timeout
        return MockMetricData(value=1.0, source=self.name)

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


# ============================================================================
# CollectionResult Tests
# ============================================================================


class TestCollectionResult:
    """Tests for CollectionResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful result."""
        data = MockMetricData(value=42.0)
        result = CollectionResult(
            success=True,
            data=data,
            collection_time_ms=10.5,
            collector_name="test",
        )

        assert result.success is True
        assert result.data == data
        assert result.error is None
        assert result.collection_time_ms == 10.5
        assert result.collector_name == "test"

    def test_failed_result(self) -> None:
        """Test creating a failed result."""
        result = CollectionResult(
            success=False,
            error="Something went wrong",
            collection_time_ms=5.0,
            collector_name="test",
        )

        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"

    def test_success_requires_data(self) -> None:
        """Test that successful results require data."""
        with pytest.raises(ValueError, match="must include data"):
            CollectionResult(success=True, collector_name="test")

    def test_failure_requires_error(self) -> None:
        """Test that failed results require error message."""
        with pytest.raises(ValueError, match="must include error"):
            CollectionResult(success=False, collector_name="test")

    def test_timestamp_defaults(self) -> None:
        """Test that timestamp defaults to now."""
        before = _utcnow()
        result = CollectionResult(success=False, error="test", collector_name="test")
        after = _utcnow()

        assert before <= result.timestamp <= after


# ============================================================================
# DataCollector Tests
# ============================================================================


class TestDataCollector:
    """Tests for DataCollector base class."""

    def test_default_values(self) -> None:
        """Test collector default values."""
        collector = MockCollector()

        assert collector.interval == 0.1
        assert collector.enabled is True
        assert collector.last_collection is None
        assert collector.consecutive_failures == 0

    def test_interval_property(self) -> None:
        """Test interval getter and setter."""
        collector = MockCollector()
        collector.interval = 2.5

        assert collector.interval == 2.5

    def test_interval_must_be_positive(self) -> None:
        """Test that interval must be positive."""
        collector = MockCollector()

        with pytest.raises(ValueError, match="must be positive"):
            collector.interval = 0

        with pytest.raises(ValueError, match="must be positive"):
            collector.interval = -1.0

    def test_enabled_property(self) -> None:
        """Test enabled getter and setter."""
        collector = MockCollector()
        collector.enabled = False

        assert collector.enabled is False

    def test_initialize(self) -> None:
        """Test initialize with config."""
        collector = MockCollector()
        collector.initialize({"interval": 5.0, "custom": "value"})

        assert collector.interval == 5.0

    def test_initialize_empty_config(self) -> None:
        """Test initialize without config."""
        collector = MockCollector()
        collector.initialize()

        assert collector.interval == collector.default_interval

    def test_shutdown(self) -> None:
        """Test shutdown."""
        collector = MockCollector()
        collector.initialize()
        collector.shutdown()

        assert collector._initialized is False

    @pytest.mark.asyncio
    async def test_collect(self) -> None:
        """Test basic collection."""
        collector = MockCollector(value=100.0)
        data = await collector.collect()

        assert isinstance(data, MockMetricData)
        assert data.value == 100.0
        assert data.source == "mock_collector"

    @pytest.mark.asyncio
    async def test_safe_collect_success(self) -> None:
        """Test safe_collect on success."""
        collector = MockCollector(value=50.0)
        result = await collector.safe_collect()

        assert result.success is True
        assert result.data is not None
        assert result.data.value == 50.0
        assert result.error is None
        assert result.collector_name == "mock_collector"
        assert result.collection_time_ms >= 0

    @pytest.mark.asyncio
    async def test_safe_collect_failure(self) -> None:
        """Test safe_collect on failure."""
        collector = FailingCollector()
        result = await collector.safe_collect()

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert "RuntimeError" in result.error
        assert "intentionally" in result.error

    @pytest.mark.asyncio
    async def test_consecutive_failures_tracking(self) -> None:
        """Test that consecutive failures are tracked."""
        collector = FailingCollector()

        await collector.safe_collect()
        assert collector.consecutive_failures == 1

        await collector.safe_collect()
        assert collector.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_success(self) -> None:
        """Test that consecutive failures reset on success."""

        # Use a collector that we can toggle
        class ToggleCollector(DataCollector[MockMetricData]):
            name = "toggle"
            should_fail = True

            async def collect(self) -> MockMetricData:
                if self.should_fail:
                    raise RuntimeError("fail")
                return MockMetricData(value=1.0)

            def get_schema(self) -> type[MockMetricData]:
                return MockMetricData

        collector = ToggleCollector()

        await collector.safe_collect()
        await collector.safe_collect()
        assert collector.consecutive_failures == 2

        collector.should_fail = False
        await collector.safe_collect()
        assert collector.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_last_collection_updated(self) -> None:
        """Test that last_collection is updated on success."""
        collector = MockCollector()

        assert collector.last_collection is None

        before = _utcnow()
        await collector.safe_collect()
        after = _utcnow()

        assert collector.last_collection is not None
        assert before <= collector.last_collection <= after

    def test_stats(self) -> None:
        """Test stats property."""
        collector = MockCollector()
        stats = collector.stats

        assert stats["name"] == "mock_collector"
        assert stats["enabled"] is True
        assert stats["interval"] == 0.1
        assert stats["total_collections"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_collections(self) -> None:
        """Test stats after some collections."""
        collector = MockCollector()

        await collector.safe_collect()
        await collector.safe_collect()

        stats = collector.stats
        assert stats["total_collections"] == 2
        assert stats["total_failures"] == 0
        assert stats["success_rate"] == 1.0

    def test_reset_stats(self) -> None:
        """Test reset_stats."""
        collector = MockCollector()
        collector._total_collections = 10
        collector._total_failures = 2
        collector._consecutive_failures = 1

        collector.reset_stats()

        assert collector._total_collections == 0
        assert collector._total_failures == 0
        assert collector._consecutive_failures == 0


# ============================================================================
# DataBuffer Tests
# ============================================================================


class TestDataBuffer:
    """Tests for DataBuffer."""

    def test_init_defaults(self) -> None:
        """Test buffer initialization with defaults."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        assert buffer.max_size == 1000
        assert buffer.max_age_seconds is None

    def test_init_custom_size(self) -> None:
        """Test buffer initialization with custom size."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_size=50)

        assert buffer.max_size == 50

    def test_init_with_max_age(self) -> None:
        """Test buffer initialization with max age."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_age_seconds=60.0)

        assert buffer.max_age_seconds == 60.0

    def test_init_invalid_size(self) -> None:
        """Test that invalid size raises error."""
        with pytest.raises(ValueError, match="must be positive"):
            DataBuffer(max_size=0)

        with pytest.raises(ValueError, match="must be positive"):
            DataBuffer(max_size=-1)

    def test_init_invalid_age(self) -> None:
        """Test that invalid age raises error."""
        with pytest.raises(ValueError, match="must be positive"):
            DataBuffer(max_age_seconds=0)

        with pytest.raises(ValueError, match="must be positive"):
            DataBuffer(max_age_seconds=-1.0)

    @pytest.mark.asyncio
    async def test_add_and_get_latest(self) -> None:
        """Test adding and retrieving latest item."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()
        data = MockMetricData(value=42.0)

        await buffer.add(data)
        latest = await buffer.get_latest()

        assert latest is not None
        assert latest.value == 42.0

    @pytest.mark.asyncio
    async def test_get_latest_empty(self) -> None:
        """Test get_latest on empty buffer."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()
        result = await buffer.get_latest()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_n(self) -> None:
        """Test getting N latest items."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        for i in range(5):
            await buffer.add(MockMetricData(value=float(i)))

        latest = await buffer.get_latest_n(3)

        assert len(latest) == 3
        # Should be newest first
        assert latest[0].value == 4.0
        assert latest[1].value == 3.0
        assert latest[2].value == 2.0

    @pytest.mark.asyncio
    async def test_get_latest_n_more_than_available(self) -> None:
        """Test get_latest_n when requesting more than available."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        await buffer.add(MockMetricData(value=1.0))
        await buffer.add(MockMetricData(value=2.0))

        latest = await buffer.get_latest_n(10)

        assert len(latest) == 2

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        """Test getting all items."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        for i in range(3):
            await buffer.add(MockMetricData(value=float(i)))

        all_items = await buffer.get_all()

        assert len(all_items) == 3
        # Should be oldest first
        assert all_items[0].value == 0.0
        assert all_items[2].value == 2.0

    @pytest.mark.asyncio
    async def test_size(self) -> None:
        """Test size method."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        assert await buffer.size() == 0

        await buffer.add(MockMetricData(value=1.0))
        assert await buffer.size() == 1

        await buffer.add(MockMetricData(value=2.0))
        assert await buffer.size() == 2

    @pytest.mark.asyncio
    async def test_is_empty(self) -> None:
        """Test is_empty method."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        assert await buffer.is_empty() is True

        await buffer.add(MockMetricData(value=1.0))
        assert await buffer.is_empty() is False

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Test clear method."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        await buffer.add(MockMetricData(value=1.0))
        await buffer.add(MockMetricData(value=2.0))
        await buffer.clear()

        assert await buffer.is_empty() is True

    @pytest.mark.asyncio
    async def test_ring_buffer_eviction(self) -> None:
        """Test that old items are evicted when buffer is full."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_size=3)

        for i in range(5):
            await buffer.add(MockMetricData(value=float(i)))

        assert await buffer.size() == 3

        all_items = await buffer.get_all()
        # Should have the last 3 items
        assert all_items[0].value == 2.0
        assert all_items[1].value == 3.0
        assert all_items[2].value == 4.0

    @pytest.mark.asyncio
    async def test_get_since(self) -> None:
        """Test getting items since a timestamp."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        old_time = _utcnow() - timedelta(seconds=10)
        recent_time = _utcnow() - timedelta(seconds=1)

        await buffer.add(MockMetricData(value=1.0, timestamp=old_time))
        await buffer.add(MockMetricData(value=2.0, timestamp=recent_time))
        await buffer.add(MockMetricData(value=3.0))  # Now

        cutoff = _utcnow() - timedelta(seconds=5)
        recent = await buffer.get_since(cutoff)

        assert len(recent) == 2
        assert recent[0].value == 2.0
        assert recent[1].value == 3.0

    @pytest.mark.asyncio
    async def test_get_in_range(self) -> None:
        """Test getting items in a time range."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        t1 = _utcnow() - timedelta(seconds=30)
        t2 = _utcnow() - timedelta(seconds=20)
        t3 = _utcnow() - timedelta(seconds=10)
        t4 = _utcnow()

        await buffer.add(MockMetricData(value=1.0, timestamp=t1))
        await buffer.add(MockMetricData(value=2.0, timestamp=t2))
        await buffer.add(MockMetricData(value=3.0, timestamp=t3))
        await buffer.add(MockMetricData(value=4.0, timestamp=t4))

        # Get items between t2 and t3
        in_range = await buffer.get_in_range(t2, t3)

        assert len(in_range) == 2
        assert in_range[0].value == 2.0
        assert in_range[1].value == 3.0

    @pytest.mark.asyncio
    async def test_age_expiration(self) -> None:
        """Test that old items expire based on age."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_age_seconds=0.1)

        await buffer.add(MockMetricData(value=1.0))
        await asyncio.sleep(0.15)  # Wait for expiration
        await buffer.add(MockMetricData(value=2.0))

        all_items = await buffer.get_all()

        # Only the recent item should remain
        assert len(all_items) == 1
        assert all_items[0].value == 2.0

    @pytest.mark.asyncio
    async def test_set_max_age(self) -> None:
        """Test updating max age setting."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_age_seconds=None)

        assert buffer.max_age_seconds is None

        await buffer.set_max_age(60.0)
        assert buffer.max_age_seconds == 60.0

        await buffer.set_max_age(None)
        assert buffer.max_age_seconds is None

    @pytest.mark.asyncio
    async def test_set_max_age_invalid(self) -> None:
        """Test that invalid max age raises error."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        with pytest.raises(ValueError, match="must be positive"):
            await buffer.set_max_age(0)

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        """Test getting buffer statistics."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_size=10)

        stats = await buffer.get_stats()
        assert stats.current_size == 0
        assert stats.max_size == 10
        assert stats.total_added == 0

        await buffer.add(MockMetricData(value=1.0))
        await buffer.add(MockMetricData(value=2.0))

        stats = await buffer.get_stats()
        assert stats.current_size == 2
        assert stats.total_added == 2
        assert stats.oldest_timestamp is not None
        assert stats.newest_timestamp is not None

    @pytest.mark.asyncio
    async def test_stats_eviction_tracking(self) -> None:
        """Test that eviction is tracked in stats."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_size=2)

        await buffer.add(MockMetricData(value=1.0))
        await buffer.add(MockMetricData(value=2.0))
        await buffer.add(MockMetricData(value=3.0))  # Should evict first

        stats = await buffer.get_stats()
        assert stats.total_evicted == 1

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Test that concurrent access is safe."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_size=100)

        async def add_items(start: int) -> None:
            for i in range(10):
                await buffer.add(MockMetricData(value=float(start + i)))

        # Run multiple concurrent add operations
        await asyncio.gather(
            add_items(0),
            add_items(100),
            add_items(200),
        )

        assert await buffer.size() == 30


# ============================================================================
# CollectionScheduler Tests
# ============================================================================


class TestCollectionScheduler:
    """Tests for CollectionScheduler."""

    def test_init_defaults(self) -> None:
        """Test scheduler initialization with defaults."""
        scheduler = CollectionScheduler()

        assert scheduler.running is False

    def test_register(self) -> None:
        """Test registering a collector."""
        scheduler = CollectionScheduler()
        collector = MockCollector()

        scheduler.register(collector)

        assert scheduler.get_collector("mock_collector") is collector
        assert scheduler.get_buffer("mock_collector") is not None

    def test_register_duplicate_raises(self) -> None:
        """Test that registering duplicate name raises error."""
        scheduler = CollectionScheduler()
        collector1 = MockCollector()
        collector2 = MockCollector()

        scheduler.register(collector1)

        with pytest.raises(ValueError, match="already registered"):
            scheduler.register(collector2)

    def test_register_custom_buffer_size(self) -> None:
        """Test registering with custom buffer size."""
        scheduler = CollectionScheduler()
        collector = MockCollector()

        scheduler.register(collector, buffer_size=50)

        buffer = scheduler.get_buffer("mock_collector")
        assert buffer is not None
        assert buffer.max_size == 50

    def test_unregister(self) -> None:
        """Test unregistering a collector."""
        scheduler = CollectionScheduler()
        collector = MockCollector()

        scheduler.register(collector)
        scheduler.unregister("mock_collector")

        assert scheduler.get_collector("mock_collector") is None

    def test_unregister_nonexistent_raises(self) -> None:
        """Test that unregistering non-existent collector raises."""
        scheduler = CollectionScheduler()

        with pytest.raises(KeyError, match="not registered"):
            scheduler.unregister("nonexistent")

    def test_list_collectors(self) -> None:
        """Test listing registered collectors."""
        scheduler = CollectionScheduler()

        # Create collectors with different names
        collector1 = MockCollector()
        collector1.name = "collector1"
        collector2 = MockCollector()
        collector2.name = "collector2"

        scheduler.register(collector1)
        scheduler.register(collector2)

        names = scheduler.list_collectors()
        assert set(names) == {"collector1", "collector2"}

    def test_get_collector_not_found(self) -> None:
        """Test get_collector returns None for unknown name."""
        scheduler = CollectionScheduler()
        result = scheduler.get_collector("unknown")

        assert result is None

    def test_get_buffer_not_found(self) -> None:
        """Test get_buffer returns None for unknown name."""
        scheduler = CollectionScheduler()
        result = scheduler.get_buffer("unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        """Test starting and stopping the scheduler."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        await scheduler.start()
        assert scheduler.running is True

        # Let it run briefly
        await asyncio.sleep(0.05)

        await scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self) -> None:
        """Test that starting multiple times is safe."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        await scheduler.start()
        await scheduler.start()  # Should be no-op
        assert scheduler.running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self) -> None:
        """Test that stopping multiple times is safe."""
        scheduler = CollectionScheduler()

        await scheduler.stop()  # Already stopped
        await scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_collect_once(self) -> None:
        """Test single collection outside schedule."""
        scheduler = CollectionScheduler()
        collector = MockCollector(value=99.0)
        scheduler.register(collector)

        result = await scheduler.collect_once("mock_collector")

        assert result.success is True
        assert result.data is not None
        assert result.data.value == 99.0

    @pytest.mark.asyncio
    async def test_collect_once_unknown_raises(self) -> None:
        """Test collect_once with unknown collector raises."""
        scheduler = CollectionScheduler()

        with pytest.raises(KeyError, match="not registered"):
            await scheduler.collect_once("unknown")

    @pytest.mark.asyncio
    async def test_collect_all_once(self) -> None:
        """Test collecting from all collectors once."""
        scheduler = CollectionScheduler()

        collector1 = MockCollector(value=1.0)
        collector1.name = "collector1"
        collector2 = MockCollector(value=2.0)
        collector2.name = "collector2"

        scheduler.register(collector1)
        scheduler.register(collector2)

        results = await scheduler.collect_all_once()

        assert len(results) == 2
        assert results["collector1"].success is True
        assert results["collector2"].success is True

    @pytest.mark.asyncio
    async def test_data_stored_in_buffer(self) -> None:
        """Test that successful collections are stored in buffer."""
        scheduler = CollectionScheduler()
        collector = MockCollector(value=42.0)
        scheduler.register(collector)

        await scheduler.collect_once("mock_collector")

        buffer = scheduler.get_buffer("mock_collector")
        assert buffer is not None

        latest = await buffer.get_latest()
        assert latest is not None
        assert latest.value == 42.0

    @pytest.mark.asyncio
    async def test_get_latest(self) -> None:
        """Test getting the latest result."""
        scheduler = CollectionScheduler()
        collector = MockCollector(value=42.0)
        scheduler.register(collector)

        await scheduler.collect_once("mock_collector")
        result = scheduler.get_latest("mock_collector")

        assert result is not None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test that slow collectors timeout."""
        scheduler = CollectionScheduler()
        collector = SlowCollector()
        scheduler.register(collector)

        result = await scheduler.collect_once("slow_collector")

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_callback_invoked(self) -> None:
        """Test that callbacks are invoked after collection."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        callback_results: list[tuple[str, CollectionResult[Any]]] = []

        async def callback(name: str, result: CollectionResult[Any]) -> None:
            callback_results.append((name, result))

        scheduler.add_callback(callback)
        await scheduler.collect_once("mock_collector")

        assert len(callback_results) == 1
        assert callback_results[0][0] == "mock_collector"
        assert callback_results[0][1].success is True

    @pytest.mark.asyncio
    async def test_remove_callback(self) -> None:
        """Test removing a callback."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        callback_count = 0

        async def callback(name: str, result: CollectionResult[Any]) -> None:
            nonlocal callback_count
            callback_count += 1

        scheduler.add_callback(callback)
        await scheduler.collect_once("mock_collector")
        assert callback_count == 1

        scheduler.remove_callback(callback)
        await scheduler.collect_once("mock_collector")
        assert callback_count == 1  # Not incremented

    @pytest.mark.asyncio
    async def test_callback_error_doesnt_break_collection(self) -> None:
        """Test that callback errors don't break collection."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        async def bad_callback(name: str, result: CollectionResult[Any]) -> None:
            raise RuntimeError("Callback failed")

        scheduler.add_callback(bad_callback)

        # Should not raise
        result = await scheduler.collect_once("mock_collector")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        """Test getting scheduler stats."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        stats = await scheduler.get_stats()

        assert stats.running is False
        assert stats.collectors_registered == 1
        assert stats.collectors_running == 0

    @pytest.mark.asyncio
    async def test_get_stats_after_collections(self) -> None:
        """Test stats after some collections."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        await scheduler.collect_once("mock_collector")
        await scheduler.collect_once("mock_collector")

        stats = await scheduler.get_stats()

        assert stats.total_collections == 2
        assert stats.total_failures == 0

    @pytest.mark.asyncio
    async def test_get_collector_stats(self) -> None:
        """Test getting detailed collector stats."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        await scheduler.collect_once("mock_collector")

        stats = await scheduler.get_collector_stats("mock_collector")

        assert stats is not None
        assert stats["collector"]["total_collections"] == 1
        assert stats["buffer"]["current_size"] == 1

    @pytest.mark.asyncio
    async def test_get_collector_stats_not_found(self) -> None:
        """Test get_collector_stats returns None for unknown."""
        scheduler = CollectionScheduler()
        result = await scheduler.get_collector_stats("unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_scheduled_collection(self) -> None:
        """Test that scheduler runs collections at intervals."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        collector.interval = 0.05  # Fast interval for testing
        scheduler.register(collector)

        await scheduler.start()
        await asyncio.sleep(0.2)  # Let it run for a bit
        await scheduler.stop()

        # Should have collected multiple times
        assert collector.collect_count >= 2

    @pytest.mark.asyncio
    async def test_disabled_collector_not_scheduled(self) -> None:
        """Test that disabled collectors don't run."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        collector.enabled = False
        scheduler.register(collector)

        await scheduler.start()
        await asyncio.sleep(0.1)
        await scheduler.stop()

        assert collector.collect_count == 0

    @pytest.mark.asyncio
    async def test_unregister_while_running(self) -> None:
        """Test unregistering a collector while scheduler is running."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        collector.interval = 0.05
        scheduler.register(collector)

        await scheduler.start()
        await asyncio.sleep(0.05)

        scheduler.unregister("mock_collector")

        # Should not raise, collector task should be cancelled
        await asyncio.sleep(0.05)
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_latency_tracking(self) -> None:
        """Test that collection latency is tracked."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        scheduler.register(collector)

        await scheduler.collect_once("mock_collector")

        stats = await scheduler.get_stats()
        assert stats.average_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_latency_tracking_overflow(self) -> None:
        """Test latency tracking when exceeding max samples."""
        scheduler = CollectionScheduler()
        collector = MockCollector()
        collector.interval = 0.001  # Very fast
        scheduler.register(collector)

        # Set a small max to test overflow behavior
        scheduler._max_latency_samples = 10

        # Collect more than max samples
        for _ in range(15):
            await scheduler.collect_once("mock_collector")

        # Should have trimmed to max samples
        assert len(scheduler._latencies) <= scheduler._max_latency_samples

        stats = await scheduler.get_stats()
        assert stats.average_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_collection_cancelled_error_propagation(self) -> None:
        """Test that CancelledError propagates correctly during collection."""

        class CancellingCollector(DataCollector[MockMetricData]):
            name = "cancelling"
            default_interval = 0.1

            async def collect(self) -> MockMetricData:
                # Simulate being cancelled during collection
                raise asyncio.CancelledError()

            def get_schema(self) -> type[MockMetricData]:
                return MockMetricData

        scheduler = CollectionScheduler()
        collector = CancellingCollector()
        scheduler.register(collector)

        # The CancelledError should propagate up
        with pytest.raises(asyncio.CancelledError):
            await scheduler.collect_once("cancelling")

    @pytest.mark.asyncio
    async def test_get_stats_running_collectors_count(self) -> None:
        """Test get_stats correctly counts running collectors."""
        scheduler = CollectionScheduler()

        collector1 = MockCollector()
        collector1.name = "collector1"
        collector1.interval = 0.5  # Slow interval
        collector2 = MockCollector()
        collector2.name = "collector2"
        collector2.interval = 0.5

        scheduler.register(collector1)
        scheduler.register(collector2)

        # Before starting, no collectors should be running
        stats = await scheduler.get_stats()
        assert stats.collectors_running == 0

        await scheduler.start()
        # Give tasks time to start
        await asyncio.sleep(0.05)

        stats = await scheduler.get_stats()
        assert stats.collectors_running == 2

        await scheduler.stop()

        stats = await scheduler.get_stats()
        assert stats.collectors_running == 0

    @pytest.mark.asyncio
    async def test_register_with_custom_buffer_age(self) -> None:
        """Test registering with custom buffer age."""
        scheduler = CollectionScheduler()
        collector = MockCollector()

        scheduler.register(collector, buffer_age=120.0)

        buffer = scheduler.get_buffer("mock_collector")
        assert buffer is not None
        assert buffer.max_age_seconds == 120.0

    def test_get_latest_not_found(self) -> None:
        """Test get_latest returns None for unknown collector."""
        scheduler = CollectionScheduler()
        result = scheduler.get_latest("unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_failed_collection_not_stored_in_buffer(self) -> None:
        """Test that failed collections are not stored in buffer."""
        scheduler = CollectionScheduler()
        collector = FailingCollector()
        scheduler.register(collector)

        await scheduler.collect_once("failing_collector")

        buffer = scheduler.get_buffer("failing_collector")
        assert buffer is not None
        assert await buffer.is_empty()


# ============================================================================
# DataBuffer Edge Case Tests
# ============================================================================


class TestDataBufferEdgeCases:
    """Additional edge case tests for DataBuffer."""

    @pytest.mark.asyncio
    async def test_stats_expiration_tracking(self) -> None:
        """Test that expiration is tracked in stats."""
        buffer: DataBuffer[MockMetricData] = DataBuffer(max_age_seconds=0.05)

        await buffer.add(MockMetricData(value=1.0))
        await asyncio.sleep(0.1)  # Wait for expiration

        # Trigger cleanup by adding another item
        await buffer.add(MockMetricData(value=2.0))

        stats = await buffer.get_stats()
        assert stats.total_expired >= 1

    @pytest.mark.asyncio
    async def test_get_in_range_empty_result(self) -> None:
        """Test get_in_range with range that matches nothing."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        now = _utcnow()
        await buffer.add(MockMetricData(value=1.0, timestamp=now))

        # Search for items before the added item
        earlier = now - timedelta(hours=2)
        even_earlier = now - timedelta(hours=3)

        result = await buffer.get_in_range(even_earlier, earlier)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_since_all_expired(self) -> None:
        """Test get_since when all items are before the cutoff."""
        buffer: DataBuffer[MockMetricData] = DataBuffer()

        old_time = _utcnow() - timedelta(hours=1)
        await buffer.add(MockMetricData(value=1.0, timestamp=old_time))

        # Search from now, which should return empty
        result = await buffer.get_since(_utcnow())
        assert len(result) == 0
