"""In-memory ring buffer for historical metric data.

This module provides an asyncio-safe ring buffer for storing collected metrics
with configurable size limits, age-based expiration, and memory management.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

from uptop.models.base import MetricData

T = TypeVar("T", bound=MetricData)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


@dataclass
class BufferStats:
    """Statistics about buffer state and usage.

    Attributes:
        current_size: Number of items currently in buffer
        max_size: Maximum buffer capacity
        total_added: Total items ever added
        total_expired: Items removed due to age
        total_evicted: Items removed due to size limit
        oldest_timestamp: Timestamp of oldest item (if any)
        newest_timestamp: Timestamp of newest item (if any)
    """

    current_size: int = 0
    max_size: int = 0
    total_added: int = 0
    total_expired: int = 0
    total_evicted: int = 0
    oldest_timestamp: datetime | None = None
    newest_timestamp: datetime | None = None


@dataclass
class BufferEntry(Generic[T]):
    """A single entry in the data buffer.

    Attributes:
        data: The metric data
        added_at: When this entry was added to the buffer
    """

    data: T
    added_at: datetime = field(default_factory=_utcnow)


class DataBuffer(Generic[T]):
    """Asyncio-safe ring buffer for historical metric data.

    Stores metric data in a fixed-size buffer with oldest entries evicted
    when capacity is reached. Supports time-based expiration and provides
    various access patterns.

    All public methods are async to ensure proper synchronization when
    accessed from multiple coroutines.

    Type Parameters:
        T: The MetricData subclass stored in this buffer

    Example:
        buffer = DataBuffer[CPUData](max_size=100, max_age_seconds=300)
        await buffer.add(cpu_data)
        latest = await buffer.get_latest()
        history = await buffer.get_all()
    """

    def __init__(
        self,
        max_size: int = 1000,
        max_age_seconds: float | None = None,
    ) -> None:
        """Initialize the buffer.

        Args:
            max_size: Maximum number of entries to store (must be positive)
            max_age_seconds: Maximum age of entries in seconds (None = no limit)

        Raises:
            ValueError: If max_size is not positive
        """
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        if max_age_seconds is not None and max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive if specified")

        self._max_size = max_size
        self._max_age_seconds = max_age_seconds
        self._buffer: deque[BufferEntry[T]] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()

        # Statistics
        self._total_added = 0
        self._total_expired = 0
        self._total_evicted = 0

    @property
    def max_size(self) -> int:
        """Get the maximum buffer size."""
        return self._max_size

    @property
    def max_age_seconds(self) -> float | None:
        """Get the maximum age in seconds (None if unlimited)."""
        return self._max_age_seconds

    async def add(self, data: T) -> None:
        """Add a new entry to the buffer.

        If the buffer is full, the oldest entry is evicted.
        Expired entries are cleaned up before adding.

        Args:
            data: The MetricData to store
        """
        async with self._lock:
            # Clean expired entries first
            self._cleanup_expired()

            # Track eviction if buffer is full
            if len(self._buffer) >= self._max_size:
                self._total_evicted += 1

            entry = BufferEntry(data=data, added_at=_utcnow())
            self._buffer.append(entry)
            self._total_added += 1

    async def get_latest(self) -> T | None:
        """Get the most recent entry.

        Returns:
            The most recent MetricData, or None if buffer is empty
        """
        async with self._lock:
            self._cleanup_expired()
            if not self._buffer:
                return None
            return self._buffer[-1].data

    async def get_latest_n(self, n: int) -> list[T]:
        """Get the N most recent entries.

        Args:
            n: Number of entries to retrieve

        Returns:
            List of MetricData, newest first (may be fewer than n)
        """
        async with self._lock:
            self._cleanup_expired()
            # Get last n entries, return in reverse order (newest first)
            entries = list(self._buffer)[-n:]
            return [e.data for e in reversed(entries)]

    async def get_all(self) -> list[T]:
        """Get all entries in the buffer.

        Returns:
            List of all MetricData, oldest first
        """
        async with self._lock:
            self._cleanup_expired()
            return [e.data for e in self._buffer]

    async def get_since(self, since: datetime) -> list[T]:
        """Get all entries since a given timestamp.

        Args:
            since: Timestamp to filter from (inclusive)

        Returns:
            List of MetricData with timestamp >= since, oldest first
        """
        async with self._lock:
            self._cleanup_expired()
            return [e.data for e in self._buffer if e.data.timestamp >= since]

    async def get_in_range(self, start: datetime, end: datetime) -> list[T]:
        """Get entries within a time range.

        Args:
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of MetricData within range, oldest first
        """
        async with self._lock:
            self._cleanup_expired()
            return [e.data for e in self._buffer if start <= e.data.timestamp <= end]

    async def size(self) -> int:
        """Get the current number of entries in the buffer.

        Returns:
            Number of entries currently stored
        """
        async with self._lock:
            self._cleanup_expired()
            return len(self._buffer)

    async def is_empty(self) -> bool:
        """Check if the buffer is empty.

        Returns:
            True if no entries are stored
        """
        async with self._lock:
            self._cleanup_expired()
            return len(self._buffer) == 0

    async def clear(self) -> None:
        """Remove all entries from the buffer."""
        async with self._lock:
            self._buffer.clear()

    async def get_stats(self) -> BufferStats:
        """Get buffer statistics.

        Returns:
            BufferStats with current state and usage info
        """
        async with self._lock:
            self._cleanup_expired()

            oldest = self._buffer[0].data.timestamp if self._buffer else None
            newest = self._buffer[-1].data.timestamp if self._buffer else None

            return BufferStats(
                current_size=len(self._buffer),
                max_size=self._max_size,
                total_added=self._total_added,
                total_expired=self._total_expired,
                total_evicted=self._total_evicted,
                oldest_timestamp=oldest,
                newest_timestamp=newest,
            )

    def _cleanup_expired(self) -> None:
        """Remove expired entries (must be called with lock held).

        This is an internal method that assumes the caller already holds
        the lock. It removes entries older than max_age_seconds.
        """
        if self._max_age_seconds is None:
            return

        cutoff = _utcnow() - timedelta(seconds=self._max_age_seconds)
        expired_count = 0

        # Remove from the front (oldest) while expired
        while self._buffer and self._buffer[0].added_at < cutoff:
            self._buffer.popleft()
            expired_count += 1

        self._total_expired += expired_count

    async def set_max_age(self, max_age_seconds: float | None) -> None:
        """Update the maximum age setting.

        Args:
            max_age_seconds: New max age in seconds (None = unlimited)

        Raises:
            ValueError: If max_age_seconds is not positive
        """
        if max_age_seconds is not None and max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive if specified")

        async with self._lock:
            self._max_age_seconds = max_age_seconds
            self._cleanup_expired()
