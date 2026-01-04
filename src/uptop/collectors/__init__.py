"""Data collection framework for uptop.

This module provides the infrastructure for collecting system metrics:

- DataCollector: Abstract base class for collectors
- DataBuffer: Ring buffer for historical data with asyncio-safe access
- CollectionScheduler: Async scheduler for per-pane data collection

All operations are asyncio-based for non-blocking performance.
"""

from uptop.collectors.base import CollectionResult, DataCollector
from uptop.collectors.buffer import BufferStats, DataBuffer
from uptop.collectors.scheduler import CollectionScheduler, SchedulerStats

__all__ = [
    "CollectionResult",
    "DataCollector",
    "DataBuffer",
    "BufferStats",
    "CollectionScheduler",
    "SchedulerStats",
]
