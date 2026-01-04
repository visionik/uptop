"""Performance profiling utilities for uptop.

This module provides profiling tools for measuring collector and render times:
- CollectorProfiler: Track collection times per collector
- RenderProfiler: Track render times per widget
- PerformanceMetrics: Aggregate performance data
- Decorators for easy profiling
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from statistics import mean, stdev
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class TimingStats:
    """Statistics for a series of timing measurements.

    Attributes:
        name: Name of the measured operation
        times_ms: List of timing measurements in milliseconds
        max_samples: Maximum number of samples to keep
    """

    name: str
    times_ms: list[float] = field(default_factory=list)
    max_samples: int = 100

    def add(self, time_ms: float) -> None:
        """Add a timing measurement.

        Args:
            time_ms: Timing in milliseconds
        """
        self.times_ms.append(time_ms)
        # Keep only the most recent samples
        if len(self.times_ms) > self.max_samples:
            self.times_ms = self.times_ms[-self.max_samples :]

    @property
    def count(self) -> int:
        """Number of measurements."""
        return len(self.times_ms)

    @property
    def avg_ms(self) -> float:
        """Average time in milliseconds."""
        if not self.times_ms:
            return 0.0
        return mean(self.times_ms)

    @property
    def min_ms(self) -> float:
        """Minimum time in milliseconds."""
        if not self.times_ms:
            return 0.0
        return min(self.times_ms)

    @property
    def max_ms(self) -> float:
        """Maximum time in milliseconds."""
        if not self.times_ms:
            return 0.0
        return max(self.times_ms)

    @property
    def std_ms(self) -> float:
        """Standard deviation in milliseconds."""
        if len(self.times_ms) < 2:
            return 0.0
        return stdev(self.times_ms)

    @property
    def last_ms(self) -> float:
        """Most recent measurement in milliseconds."""
        if not self.times_ms:
            return 0.0
        return self.times_ms[-1]

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary.

        Returns:
            Dictionary with stats summary
        """
        return {
            "name": self.name,
            "count": self.count,
            "avg_ms": round(self.avg_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "std_ms": round(self.std_ms, 3),
            "last_ms": round(self.last_ms, 3),
        }

    def reset(self) -> None:
        """Clear all timing measurements."""
        self.times_ms.clear()


class CollectorProfiler:
    """Profiler for data collector operations.

    Tracks collection times per collector and provides aggregate statistics.
    """

    def __init__(self) -> None:
        """Initialize the collector profiler."""
        self._stats: dict[str, TimingStats] = {}
        self._enabled: bool = False

    @property
    def enabled(self) -> bool:
        """Check if profiling is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable profiling."""
        self._enabled = True
        logger.info("Collector profiling enabled")

    def disable(self) -> None:
        """Disable profiling."""
        self._enabled = False
        logger.info("Collector profiling disabled")

    def record(self, collector_name: str, time_ms: float) -> None:
        """Record a collection time.

        Args:
            collector_name: Name of the collector
            time_ms: Collection time in milliseconds
        """
        if not self._enabled:
            return

        if collector_name not in self._stats:
            self._stats[collector_name] = TimingStats(name=collector_name)

        self._stats[collector_name].add(time_ms)

        # Log slow collections
        if time_ms > 100:  # More than 100ms is considered slow
            logger.warning(
                f"Slow collection detected: {collector_name} took {time_ms:.1f}ms"
            )

    def get_stats(self, collector_name: str) -> TimingStats | None:
        """Get stats for a specific collector.

        Args:
            collector_name: Name of the collector

        Returns:
            TimingStats or None if no data
        """
        return self._stats.get(collector_name)

    def get_all_stats(self) -> dict[str, TimingStats]:
        """Get all collector stats.

        Returns:
            Dictionary mapping collector names to their stats
        """
        return dict(self._stats)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all collector performance.

        Returns:
            Dictionary with summary data
        """
        return {
            "enabled": self._enabled,
            "collectors": {name: stats.to_dict() for name, stats in self._stats.items()},
        }

    def reset(self) -> None:
        """Reset all profiling data."""
        for stats in self._stats.values():
            stats.reset()

    def clear(self) -> None:
        """Clear all profiling data and stats."""
        self._stats.clear()


class RenderProfiler:
    """Profiler for TUI render operations.

    Tracks render times per widget and provides aggregate statistics.
    """

    def __init__(self) -> None:
        """Initialize the render profiler."""
        self._stats: dict[str, TimingStats] = {}
        self._enabled: bool = False
        self._frame_times: TimingStats = TimingStats(name="frame")

    @property
    def enabled(self) -> bool:
        """Check if profiling is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable profiling."""
        self._enabled = True
        logger.info("Render profiling enabled")

    def disable(self) -> None:
        """Disable profiling."""
        self._enabled = False
        logger.info("Render profiling disabled")

    def record_widget(self, widget_name: str, time_ms: float) -> None:
        """Record a widget render time.

        Args:
            widget_name: Name of the widget
            time_ms: Render time in milliseconds
        """
        if not self._enabled:
            return

        if widget_name not in self._stats:
            self._stats[widget_name] = TimingStats(name=widget_name)

        self._stats[widget_name].add(time_ms)

        # Log slow renders
        if time_ms > 50:  # More than 50ms is considered slow for a widget
            logger.warning(
                f"Slow render detected: {widget_name} took {time_ms:.1f}ms"
            )

    def record_frame(self, time_ms: float) -> None:
        """Record a frame render time.

        Args:
            time_ms: Total frame time in milliseconds
        """
        if not self._enabled:
            return

        self._frame_times.add(time_ms)

        # Log if we're dropping below 30fps (>33ms per frame)
        if time_ms > 33:
            logger.warning(f"Frame time exceeded 33ms: {time_ms:.1f}ms")

    def get_stats(self, widget_name: str) -> TimingStats | None:
        """Get stats for a specific widget.

        Args:
            widget_name: Name of the widget

        Returns:
            TimingStats or None if no data
        """
        return self._stats.get(widget_name)

    def get_frame_stats(self) -> TimingStats:
        """Get frame timing stats.

        Returns:
            TimingStats for frame times
        """
        return self._frame_times

    def get_all_stats(self) -> dict[str, TimingStats]:
        """Get all widget stats.

        Returns:
            Dictionary mapping widget names to their stats
        """
        return dict(self._stats)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all render performance.

        Returns:
            Dictionary with summary data
        """
        return {
            "enabled": self._enabled,
            "frame": self._frame_times.to_dict(),
            "widgets": {name: stats.to_dict() for name, stats in self._stats.items()},
        }

    def reset(self) -> None:
        """Reset all profiling data."""
        for stats in self._stats.values():
            stats.reset()
        self._frame_times.reset()

    def clear(self) -> None:
        """Clear all profiling data and stats."""
        self._stats.clear()
        self._frame_times = TimingStats(name="frame")


@dataclass
class PerformanceMetrics:
    """Aggregate performance metrics for the application.

    Combines collector and render profiling data.
    """

    collector_profiler: CollectorProfiler = field(default_factory=CollectorProfiler)
    render_profiler: RenderProfiler = field(default_factory=RenderProfiler)

    def enable_all(self) -> None:
        """Enable all profiling."""
        self.collector_profiler.enable()
        self.render_profiler.enable()

    def disable_all(self) -> None:
        """Disable all profiling."""
        self.collector_profiler.disable()
        self.render_profiler.disable()

    def get_summary(self) -> dict[str, Any]:
        """Get a complete performance summary.

        Returns:
            Dictionary with all performance data
        """
        return {
            "collectors": self.collector_profiler.get_summary(),
            "render": self.render_profiler.get_summary(),
        }

    def reset_all(self) -> None:
        """Reset all profiling data."""
        self.collector_profiler.reset()
        self.render_profiler.reset()

    def format_report(self) -> str:
        """Format a human-readable performance report.

        Returns:
            Formatted report string
        """
        lines = ["Performance Report", "=" * 50, ""]

        # Collector stats
        lines.append("Collector Timing:")
        lines.append("-" * 30)
        for name, stats in self.collector_profiler.get_all_stats().items():
            lines.append(
                f"  {name}: avg={stats.avg_ms:.1f}ms "
                f"min={stats.min_ms:.1f}ms max={stats.max_ms:.1f}ms "
                f"(n={stats.count})"
            )

        lines.append("")

        # Render stats
        lines.append("Render Timing:")
        lines.append("-" * 30)
        frame_stats = self.render_profiler.get_frame_stats()
        if frame_stats.count > 0:
            fps = 1000.0 / frame_stats.avg_ms if frame_stats.avg_ms > 0 else 0
            lines.append(
                f"  Frame: avg={frame_stats.avg_ms:.1f}ms "
                f"({fps:.1f} FPS theoretical)"
            )

        for name, stats in self.render_profiler.get_all_stats().items():
            lines.append(
                f"  {name}: avg={stats.avg_ms:.1f}ms "
                f"min={stats.min_ms:.1f}ms max={stats.max_ms:.1f}ms "
                f"(n={stats.count})"
            )

        return "\n".join(lines)


# Global profiler instance
_global_profiler: PerformanceMetrics | None = None


def get_profiler() -> PerformanceMetrics:
    """Get the global performance metrics instance.

    Returns:
        The global PerformanceMetrics instance
    """
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceMetrics()
    return _global_profiler


def reset_profiler() -> None:
    """Reset the global profiler."""
    global _global_profiler
    _global_profiler = None


def profile_async(collector_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to profile async collector functions.

    Args:
        collector_name: Name to use for this collector in profiling

    Returns:
        Decorator function

    Example:
        >>> @profile_async("cpu")
        ... async def collect(self) -> CPUData:
        ...     return await self._collect_impl()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            profiler = get_profiler()
            if not profiler.collector_profiler.enabled:
                return await func(*args, **kwargs)  # type: ignore

            start = time.monotonic()
            try:
                return await func(*args, **kwargs)  # type: ignore
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000
                profiler.collector_profiler.record(collector_name, elapsed_ms)

        return wrapper  # type: ignore

    return decorator


def profile_render(widget_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to profile render functions.

    Args:
        widget_name: Name to use for this widget in profiling

    Returns:
        Decorator function

    Example:
        >>> @profile_render("cpu_widget")
        ... def render(self) -> RenderableType:
        ...     return self._render_impl()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            profiler = get_profiler()
            if not profiler.render_profiler.enabled:
                return func(*args, **kwargs)

            start = time.monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000
                profiler.render_profiler.record_widget(widget_name, elapsed_ms)

        return wrapper

    return decorator
