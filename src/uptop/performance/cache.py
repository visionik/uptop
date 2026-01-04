"""Caching utilities for performance optimization.

This module provides caching mechanisms for expensive operations:
- CachedValue: Time-based value caching
- lru_cache_timed: LRU cache with time-based expiration
- cached_system_info: Pre-cached system information that rarely changes
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache, wraps
from typing import Any, Callable, Generic, TypeVar

import psutil

T = TypeVar("T")


@dataclass
class CachedValue(Generic[T]):
    """A value that is cached for a specified duration.

    Thread-safe cache for values that are expensive to compute
    but don't change frequently.

    Attributes:
        value: The cached value (None if not yet computed)
        ttl_seconds: How long the cache is valid
        last_update: Monotonic timestamp of last update

    Example:
        >>> cpu_count = CachedValue[int](ttl_seconds=60.0)
        >>> def get_cpu_count():
        ...     if cpu_count.is_valid:
        ...         return cpu_count.value
        ...     result = psutil.cpu_count()
        ...     cpu_count.update(result)
        ...     return result
    """

    ttl_seconds: float = 60.0
    value: T | None = field(default=None, repr=False)
    last_update: float = field(default=0.0, repr=False)

    @property
    def is_valid(self) -> bool:
        """Check if the cached value is still valid."""
        if self.value is None:
            return False
        return (time.monotonic() - self.last_update) < self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get the age of the cached value in seconds."""
        if self.last_update == 0.0:
            return float("inf")
        return time.monotonic() - self.last_update

    def update(self, value: T) -> None:
        """Update the cached value.

        Args:
            value: The new value to cache
        """
        self.value = value
        self.last_update = time.monotonic()

    def invalidate(self) -> None:
        """Invalidate the cache, forcing refresh on next access."""
        self.value = None
        self.last_update = 0.0

    def get_or_compute(self, compute_fn: Callable[[], T]) -> T:
        """Get the cached value or compute it if expired.

        Args:
            compute_fn: Function to compute the value if cache is invalid

        Returns:
            The cached or newly computed value
        """
        if self.is_valid:
            return self.value  # type: ignore
        value = compute_fn()
        self.update(value)
        return value


def lru_cache_timed(
    maxsize: int = 128,
    ttl_seconds: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """LRU cache decorator with time-based expiration.

    Combines functools.lru_cache with time-based invalidation.

    Args:
        maxsize: Maximum cache size (passed to lru_cache)
        ttl_seconds: Time-to-live for cache entries in seconds

    Returns:
        Decorator function

    Example:
        >>> @lru_cache_timed(maxsize=1, ttl_seconds=10.0)
        ... def get_cpu_info():
        ...     return psutil.cpu_count()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Internal state for TTL tracking
        last_update: float = 0.0

        @lru_cache(maxsize=maxsize)
        def cached_func(*args: Any, **kwargs: Any) -> T:
            return func(*args, **kwargs)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal last_update
            current_time = time.monotonic()

            # Check if cache should be invalidated
            if (current_time - last_update) >= ttl_seconds:
                cached_func.cache_clear()
                last_update = current_time

            return cached_func(*args, **kwargs)

        # Expose cache control methods
        wrapper.cache_clear = cached_func.cache_clear  # type: ignore
        wrapper.cache_info = cached_func.cache_info  # type: ignore

        return wrapper

    return decorator


class SystemInfoCache:
    """Cached system information that rarely changes.

    Provides cached access to expensive system calls that return
    values that don't change during runtime (or change very rarely).

    This is a singleton-like class with class-level caching.
    """

    _cpu_count: CachedValue[int] = CachedValue(ttl_seconds=3600.0)  # 1 hour
    _cpu_count_logical: CachedValue[int] = CachedValue(ttl_seconds=3600.0)
    _boot_time: CachedValue[float] = CachedValue(ttl_seconds=float("inf"))  # Never expires
    _total_memory: CachedValue[int] = CachedValue(ttl_seconds=3600.0)
    _total_swap: CachedValue[int] = CachedValue(ttl_seconds=60.0)

    @classmethod
    def cpu_count(cls, logical: bool = True) -> int:
        """Get CPU count with caching.

        Args:
            logical: If True, return logical CPUs, else physical

        Returns:
            Number of CPUs
        """
        if logical:
            return cls._cpu_count_logical.get_or_compute(
                lambda: psutil.cpu_count(logical=True) or 1
            )
        return cls._cpu_count.get_or_compute(lambda: psutil.cpu_count(logical=False) or 1)

    @classmethod
    def boot_time(cls) -> float:
        """Get system boot time with caching.

        Returns:
            Unix timestamp of system boot
        """
        return cls._boot_time.get_or_compute(psutil.boot_time)

    @classmethod
    def total_memory(cls) -> int:
        """Get total system memory with caching.

        Returns:
            Total memory in bytes
        """
        return cls._total_memory.get_or_compute(lambda: psutil.virtual_memory().total)

    @classmethod
    def total_swap(cls) -> int:
        """Get total swap space with caching.

        Returns:
            Total swap in bytes
        """
        return cls._total_swap.get_or_compute(lambda: psutil.swap_memory().total)

    @classmethod
    def invalidate_all(cls) -> None:
        """Invalidate all cached system info."""
        cls._cpu_count.invalidate()
        cls._cpu_count_logical.invalidate()
        cls._boot_time.invalidate()
        cls._total_memory.invalidate()
        cls._total_swap.invalidate()


# Module-level convenience function
def cached_system_info() -> SystemInfoCache:
    """Get the system info cache instance.

    Returns:
        The SystemInfoCache class (used for accessing cached values)
    """
    return SystemInfoCache
