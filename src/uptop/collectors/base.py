"""Abstract base class for data collectors.

This module defines the DataCollector interface that all collectors must implement.
Collectors are responsible for gathering metrics asynchronously with proper
error handling and interval management.
"""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any, Generic, TypeVar

from uptop.models.base import MetricData

T = TypeVar("T", bound=MetricData)

# Logger for collector operations - debug level for permission/access issues
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


@dataclass
class CollectionResult(Generic[T]):
    """Result of a data collection attempt.

    Encapsulates both successful collections and failures with metadata
    about the collection process.

    Attributes:
        success: Whether the collection succeeded
        data: The collected MetricData (None if failed)
        error: Error message if collection failed
        collection_time_ms: How long the collection took in milliseconds
        timestamp: When the collection was attempted
        collector_name: Name of the collector that produced this result
    """

    success: bool
    data: T | None = None
    error: str | None = None
    collection_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=_utcnow)
    collector_name: str = ""

    def __post_init__(self) -> None:
        """Validate result consistency."""
        if self.success and self.data is None:
            raise ValueError("Successful collection must include data")
        if not self.success and self.error is None:
            raise ValueError("Failed collection must include error message")


class DataCollector(ABC, Generic[T]):
    """Abstract base class for data collectors.

    Collectors gather metrics from various sources (CPU, memory, disk, etc.)
    and return them as typed MetricData subclasses. All collection is async
    to avoid blocking the event loop.

    Type Parameters:
        T: The MetricData subclass this collector produces

    Class Attributes:
        name: Unique identifier for this collector
        default_interval: Default collection interval in seconds
        timeout: Maximum time allowed for a single collection in seconds

    Example:
        class CPUCollector(DataCollector[CPUData]):
            name = "cpu"
            default_interval = 1.0
            timeout = 5.0

            async def collect(self) -> CPUData:
                # Gather CPU metrics
                return CPUData(...)

            def get_schema(self) -> type[CPUData]:
                return CPUData
    """

    name: str = "unnamed_collector"
    default_interval: float = 1.0
    timeout: float = 5.0

    def __init__(self) -> None:
        """Initialize the collector with default state."""
        self._interval: float = self.default_interval
        self._enabled: bool = True
        self._initialized: bool = False
        self._config: dict[str, Any] = {}
        self._last_collection: datetime | None = None
        self._consecutive_failures: int = 0
        self._total_collections: int = 0
        self._total_failures: int = 0

    @property
    def interval(self) -> float:
        """Get the current collection interval in seconds."""
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        """Set the collection interval in seconds.

        Args:
            value: Interval in seconds (must be positive)

        Raises:
            ValueError: If interval is not positive
        """
        if value <= 0:
            raise ValueError("Interval must be positive")
        self._interval = value

    @property
    def enabled(self) -> bool:
        """Check if the collector is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable the collector."""
        self._enabled = value

    @property
    def last_collection(self) -> datetime | None:
        """Get the timestamp of the last successful collection."""
        return self._last_collection

    @property
    def consecutive_failures(self) -> int:
        """Get the count of consecutive collection failures."""
        return self._consecutive_failures

    @property
    def stats(self) -> dict[str, Any]:
        """Get collector statistics.

        Returns:
            Dictionary with collection stats
        """
        return {
            "name": self.name,
            "enabled": self._enabled,
            "interval": self._interval,
            "total_collections": self._total_collections,
            "total_failures": self._total_failures,
            "consecutive_failures": self._consecutive_failures,
            "last_collection": self._last_collection,
            "success_rate": (
                (self._total_collections - self._total_failures) / self._total_collections
                if self._total_collections > 0
                else 0.0
            ),
        }

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the collector with configuration.

        Called once after the collector is created but before collection starts.
        Override this to perform setup that requires configuration.

        Args:
            config: Collector-specific configuration
        """
        self._config = config or {}
        if "interval" in self._config:
            self.interval = float(self._config["interval"])
        self._initialized = True

    def shutdown(self) -> None:
        """Clean up collector resources.

        Called when the collector is being stopped or removed.
        Override this to release resources, close connections, etc.
        """
        self._initialized = False

    @abstractmethod
    async def collect(self) -> T:
        """Collect current metrics.

        This is the core method that gathers data. Must be implemented by
        subclasses. Should be async to avoid blocking.

        Returns:
            A MetricData subclass instance with current metrics

        Raises:
            Exception: Collection errors are caught and wrapped in CollectionResult
        """
        ...

    @abstractmethod
    def get_schema(self) -> type[T]:
        """Return the Pydantic model class for this collector's data.

        Used for validation and JSON schema generation.

        Returns:
            The MetricData subclass produced by collect()
        """
        ...

    async def safe_collect(self) -> CollectionResult[T]:
        """Collect data with error handling and timing.

        Wraps collect() with try/except and measures collection time.
        Updates internal statistics on success/failure.

        Returns:
            CollectionResult with data or error information
        """
        start_time = _utcnow()
        self._total_collections += 1

        try:
            data = await self.collect()
            elapsed_ms = (_utcnow() - start_time).total_seconds() * 1000

            self._last_collection = _utcnow()
            self._consecutive_failures = 0

            return CollectionResult(
                success=True,
                data=data,
                collection_time_ms=elapsed_ms,
                timestamp=start_time,
                collector_name=self.name,
            )

        except PermissionError as e:
            # Log permission errors at debug level to avoid spamming
            logger.debug(
                "Permission denied in collector '%s': %s",
                self.name,
                str(e),
            )
            elapsed_ms = (_utcnow() - start_time).total_seconds() * 1000
            self._consecutive_failures += 1
            self._total_failures += 1

            return CollectionResult(
                success=False,
                error=f"Permission denied: {e!s}",
                collection_time_ms=elapsed_ms,
                timestamp=start_time,
                collector_name=self.name,
            )

        except Exception as e:
            elapsed_ms = (_utcnow() - start_time).total_seconds() * 1000
            self._consecutive_failures += 1
            self._total_failures += 1

            return CollectionResult(
                success=False,
                error=f"{type(e).__name__}: {e!s}",
                collection_time_ms=elapsed_ms,
                timestamp=start_time,
                collector_name=self.name,
            )

    async def collect_with_retry(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
    ) -> CollectionResult[T]:
        """Collect data with automatic retry on transient failures.

        Implements exponential backoff for retries. On each failure, waits
        longer before the next attempt: base_delay * (attempt + 1).

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds between retries (default: 0.5)

        Returns:
            CollectionResult with data or error information from the last attempt

        Example:
            result = await collector.collect_with_retry(max_retries=3)
            if result.success:
                print(f"Got data: {result.data}")
            else:
                print(f"Failed after retries: {result.error}")
        """
        last_result: CollectionResult[T] | None = None

        for attempt in range(max_retries):
            result = await self.safe_collect()
            last_result = result

            if result.success:
                return result

            # Don't retry on permission errors - they won't resolve themselves
            if result.error and "Permission denied" in result.error:
                logger.debug(
                    "Collector '%s': Not retrying permission error",
                    self.name,
                )
                return result

            # Log retry attempts at debug level
            if attempt < max_retries - 1:
                delay = base_delay * (attempt + 1)
                logger.debug(
                    "Collector '%s': Attempt %d/%d failed, retrying in %.1fs: %s",
                    self.name,
                    attempt + 1,
                    max_retries,
                    delay,
                    result.error,
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    "Collector '%s': Collection failed after %d attempts: %s",
                    self.name,
                    max_retries,
                    result.error,
                )

        # Should always have a result, but be safe
        if last_result is None:
            return CollectionResult(
                success=False,
                error="No collection attempts made",
                collector_name=self.name,
            )

        return last_result

    def reset_stats(self) -> None:
        """Reset all collection statistics."""
        self._consecutive_failures = 0
        self._total_collections = 0
        self._total_failures = 0
        self._last_collection = None
