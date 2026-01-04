"""Performance optimization utilities for uptop.

This module provides:
- Profiling decorators for timing collectors and render cycles
- Caching utilities for expensive operations
- Performance metrics collection and reporting
- Debug mode utilities for performance analysis
"""

from uptop.performance.cache import CachedValue, cached_system_info, lru_cache_timed
from uptop.performance.profiler import (
    CollectorProfiler,
    PerformanceMetrics,
    RenderProfiler,
    get_profiler,
    profile_async,
    profile_render,
    reset_profiler,
)

__all__ = [
    # Cache utilities
    "CachedValue",
    "cached_system_info",
    "lru_cache_timed",
    # Profiler utilities
    "CollectorProfiler",
    "PerformanceMetrics",
    "RenderProfiler",
    "get_profiler",
    "profile_async",
    "profile_render",
    "reset_profiler",
]
