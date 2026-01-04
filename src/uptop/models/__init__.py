"""Pydantic data models for uptop.

This module provides the core data models used throughout uptop:
- MetricData: Base class for all metric data
- SystemSnapshot: Point-in-time system state
- PluginMetadata: Plugin registration information
- MetricType: Semantic metric types (counter, gauge, histogram, summary)
- Counter, Gauge, etc.: Type aliases for annotated metric fields
- counter_field, gauge_field, etc.: Field factories with metric type metadata
"""

from uptop.models.base import (
    Counter,
    CounterFloat,
    DisplayMode,
    Gauge,
    GaugeInt,
    MetricData,
    MetricType,
    PluginMetadata,
    PluginType,
    SystemSnapshot,
    counter_field,
    gauge_field,
    get_all_metric_types,
    get_metric_type,
    histogram_field,
    summary_field,
)

__all__ = [
    # Base models
    "MetricData",
    "SystemSnapshot",
    "PluginMetadata",
    "PluginType",
    # Metric types
    "MetricType",
    # Display modes
    "DisplayMode",
    # Type aliases
    "Counter",
    "CounterFloat",
    "Gauge",
    "GaugeInt",
    # Field factories
    "counter_field",
    "gauge_field",
    "histogram_field",
    "summary_field",
    # Introspection
    "get_metric_type",
    "get_all_metric_types",
]
