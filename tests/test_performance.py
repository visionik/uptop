"""Tests for the performance optimization module."""

import time

import pytest

from uptop.performance import (
    CachedValue,
    CollectorProfiler,
    PerformanceMetrics,
    RenderProfiler,
    get_profiler,
    lru_cache_timed,
    reset_profiler,
)
from uptop.performance.cache import SystemInfoCache
from uptop.performance.profiler import TimingStats


class TestCachedValue:
    """Tests for CachedValue class."""

    def test_initial_state(self) -> None:
        """Test that a new CachedValue is invalid."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=1.0)
        assert not cache.is_valid
        assert cache.value is None

    def test_update_makes_valid(self) -> None:
        """Test that updating a value makes the cache valid."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=60.0)
        cache.update(42)
        assert cache.is_valid
        assert cache.value == 42

    def test_cache_expires(self) -> None:
        """Test that cache expires after TTL."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=0.01)  # 10ms
        cache.update(42)
        assert cache.is_valid

        time.sleep(0.02)  # Wait for expiration
        assert not cache.is_valid

    def test_invalidate(self) -> None:
        """Test manual cache invalidation."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=60.0)
        cache.update(42)
        assert cache.is_valid

        cache.invalidate()
        assert not cache.is_valid
        assert cache.value is None

    def test_get_or_compute_cached(self) -> None:
        """Test get_or_compute returns cached value."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=60.0)
        call_count = 0

        def compute() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        # First call should compute
        result1 = cache.get_or_compute(compute)
        assert result1 == 42
        assert call_count == 1

        # Second call should use cache
        result2 = cache.get_or_compute(compute)
        assert result2 == 42
        assert call_count == 1  # Not incremented

    def test_get_or_compute_expired(self) -> None:
        """Test get_or_compute recomputes after expiration."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=0.01)
        call_count = 0

        def compute() -> int:
            nonlocal call_count
            call_count += 1
            return 42 + call_count

        # First call
        result1 = cache.get_or_compute(compute)
        assert result1 == 43
        assert call_count == 1

        # Wait for expiration
        time.sleep(0.02)

        # Second call should recompute
        result2 = cache.get_or_compute(compute)
        assert result2 == 44
        assert call_count == 2

    def test_age_seconds(self) -> None:
        """Test age_seconds property."""
        cache: CachedValue[int] = CachedValue(ttl_seconds=60.0)

        # Before any update, age is infinite
        assert cache.age_seconds == float("inf")

        cache.update(42)
        assert cache.age_seconds >= 0.0
        assert cache.age_seconds < 1.0  # Should be very small


class TestLruCacheTimed:
    """Tests for lru_cache_timed decorator."""

    def test_caching(self) -> None:
        """Test that values are cached."""
        call_count = 0

        @lru_cache_timed(maxsize=1, ttl_seconds=60.0)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should be cached
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1

    def test_cache_expires(self) -> None:
        """Test that cache expires after TTL."""
        call_count = 0

        @lru_cache_timed(maxsize=1, ttl_seconds=0.01)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert call_count == 1

        # Wait for expiration
        time.sleep(0.02)

        # Call should recompute
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 2


class TestSystemInfoCache:
    """Tests for SystemInfoCache class."""

    def test_cpu_count(self) -> None:
        """Test CPU count caching."""
        count1 = SystemInfoCache.cpu_count(logical=True)
        count2 = SystemInfoCache.cpu_count(logical=True)
        assert count1 == count2
        assert count1 >= 1

    def test_boot_time(self) -> None:
        """Test boot time caching."""
        boot1 = SystemInfoCache.boot_time()
        boot2 = SystemInfoCache.boot_time()
        assert boot1 == boot2
        assert boot1 > 0

    def test_total_memory(self) -> None:
        """Test total memory caching."""
        mem1 = SystemInfoCache.total_memory()
        mem2 = SystemInfoCache.total_memory()
        assert mem1 == mem2
        assert mem1 > 0


class TestTimingStats:
    """Tests for TimingStats class."""

    def test_initial_state(self) -> None:
        """Test initial state of TimingStats."""
        stats = TimingStats(name="test")
        assert stats.count == 0
        assert stats.avg_ms == 0.0
        assert stats.min_ms == 0.0
        assert stats.max_ms == 0.0
        assert stats.std_ms == 0.0
        assert stats.last_ms == 0.0

    def test_add_single(self) -> None:
        """Test adding a single measurement."""
        stats = TimingStats(name="test")
        stats.add(10.0)

        assert stats.count == 1
        assert stats.avg_ms == 10.0
        assert stats.min_ms == 10.0
        assert stats.max_ms == 10.0
        assert stats.last_ms == 10.0
        assert stats.std_ms == 0.0  # No std with single value

    def test_add_multiple(self) -> None:
        """Test adding multiple measurements."""
        stats = TimingStats(name="test")
        stats.add(10.0)
        stats.add(20.0)
        stats.add(30.0)

        assert stats.count == 3
        assert stats.avg_ms == 20.0
        assert stats.min_ms == 10.0
        assert stats.max_ms == 30.0
        assert stats.last_ms == 30.0
        assert stats.std_ms > 0.0

    def test_max_samples(self) -> None:
        """Test that old samples are removed when max_samples is reached."""
        stats = TimingStats(name="test", max_samples=3)
        stats.add(10.0)
        stats.add(20.0)
        stats.add(30.0)
        stats.add(40.0)  # This should push out 10.0

        assert stats.count == 3
        assert stats.min_ms == 20.0  # 10.0 was removed
        assert stats.max_ms == 40.0

    def test_reset(self) -> None:
        """Test resetting stats."""
        stats = TimingStats(name="test")
        stats.add(10.0)
        stats.add(20.0)
        stats.reset()

        assert stats.count == 0
        assert stats.avg_ms == 0.0

    def test_to_dict(self) -> None:
        """Test converting stats to dictionary."""
        stats = TimingStats(name="test")
        stats.add(10.0)

        result = stats.to_dict()
        assert result["name"] == "test"
        assert result["count"] == 1
        assert result["avg_ms"] == 10.0


class TestCollectorProfiler:
    """Tests for CollectorProfiler class."""

    def test_disabled_by_default(self) -> None:
        """Test that profiler is disabled by default."""
        profiler = CollectorProfiler()
        assert not profiler.enabled

    def test_enable_disable(self) -> None:
        """Test enabling and disabling profiler."""
        profiler = CollectorProfiler()

        profiler.enable()
        assert profiler.enabled

        profiler.disable()
        assert not profiler.enabled

    def test_record_when_disabled(self) -> None:
        """Test that recording does nothing when disabled."""
        profiler = CollectorProfiler()
        profiler.record("cpu", 10.0)

        assert profiler.get_stats("cpu") is None

    def test_record_when_enabled(self) -> None:
        """Test recording when enabled."""
        profiler = CollectorProfiler()
        profiler.enable()
        profiler.record("cpu", 10.0)
        profiler.record("cpu", 20.0)

        stats = profiler.get_stats("cpu")
        assert stats is not None
        assert stats.count == 2
        assert stats.avg_ms == 15.0

    def test_get_all_stats(self) -> None:
        """Test getting all stats."""
        profiler = CollectorProfiler()
        profiler.enable()
        profiler.record("cpu", 10.0)
        profiler.record("memory", 5.0)

        all_stats = profiler.get_all_stats()
        assert "cpu" in all_stats
        assert "memory" in all_stats

    def test_reset(self) -> None:
        """Test resetting profiler."""
        profiler = CollectorProfiler()
        profiler.enable()
        profiler.record("cpu", 10.0)
        profiler.reset()

        stats = profiler.get_stats("cpu")
        assert stats is not None
        assert stats.count == 0

    def test_clear(self) -> None:
        """Test clearing profiler."""
        profiler = CollectorProfiler()
        profiler.enable()
        profiler.record("cpu", 10.0)
        profiler.clear()

        assert profiler.get_stats("cpu") is None


class TestRenderProfiler:
    """Tests for RenderProfiler class."""

    def test_record_widget(self) -> None:
        """Test recording widget render time."""
        profiler = RenderProfiler()
        profiler.enable()
        profiler.record_widget("cpu_widget", 5.0)

        stats = profiler.get_stats("cpu_widget")
        assert stats is not None
        assert stats.count == 1
        assert stats.avg_ms == 5.0

    def test_record_frame(self) -> None:
        """Test recording frame time."""
        profiler = RenderProfiler()
        profiler.enable()
        profiler.record_frame(16.0)
        profiler.record_frame(17.0)

        frame_stats = profiler.get_frame_stats()
        assert frame_stats.count == 2


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics class."""

    def test_enable_all(self) -> None:
        """Test enabling all profilers."""
        metrics = PerformanceMetrics()
        metrics.enable_all()

        assert metrics.collector_profiler.enabled
        assert metrics.render_profiler.enabled

    def test_disable_all(self) -> None:
        """Test disabling all profilers."""
        metrics = PerformanceMetrics()
        metrics.enable_all()
        metrics.disable_all()

        assert not metrics.collector_profiler.enabled
        assert not metrics.render_profiler.enabled

    def test_format_report(self) -> None:
        """Test generating performance report."""
        metrics = PerformanceMetrics()
        metrics.enable_all()
        metrics.collector_profiler.record("cpu", 10.0)
        metrics.render_profiler.record_frame(16.0)

        report = metrics.format_report()
        assert "Performance Report" in report
        assert "cpu" in report
        assert "Frame" in report


class TestGlobalProfiler:
    """Tests for global profiler functions."""

    def test_get_profiler(self) -> None:
        """Test getting global profiler."""
        reset_profiler()  # Clear any existing profiler
        profiler1 = get_profiler()
        profiler2 = get_profiler()

        assert profiler1 is profiler2

    def test_reset_profiler(self) -> None:
        """Test resetting global profiler."""
        profiler1 = get_profiler()
        reset_profiler()
        profiler2 = get_profiler()

        assert profiler1 is not profiler2
