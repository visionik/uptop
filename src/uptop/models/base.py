"""Base Pydantic models for uptop data types.

This module defines the foundational data models that all uptop components use:
- MetricData: Base class for all collected metrics
- SystemSnapshot: Complete system state at a point in time
- PluginMetadata: Information about registered plugins
- MetricType: Enum for semantic metric types (counter, gauge, histogram, summary)
- Counter, Gauge: Annotated type aliases for typed metric fields
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo


class MetricType(str, Enum):
    """Semantic types for metrics following Prometheus conventions.

    These types define how a metric behaves over time and how it should
    be processed for aggregation, rate calculation, and visualization.

    Attributes:
        COUNTER: Monotonically increasing value that only goes up (may reset to zero).
                 Used for: total bytes sent, request count, errors, jobs processed.
                 Aggregation: sum, rate calculation: delta/time.
        GAUGE: Value that can go up and down, representing current state.
               Used for: memory usage, CPU percent, temperature, queue length.
               Aggregation: avg/min/max/last, no rate calculation needed.
        HISTOGRAM: Observations bucketed into configurable ranges plus count/sum.
                   Used for: request latency distribution, payload sizes.
                   Aggregation: bucket merging, percentile calculation.
        SUMMARY: Streaming quantiles over sliding time window plus count/sum.
                 Used for: 95th percentile latency, real-time quantiles.
                 Aggregation: quantile recalculation over window.
    """

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class DisplayMode(str, Enum):
    """Display density modes for panes.

    Controls how much information is shown in each pane:
    - MICRO: Ultra-compact, single line or icon only
    - MINIMIZED: Essential information only, very compact display
    - MEDIUM: Standard display with key details (default)
    - MAXIMIZED: Full detail display with all available information

    Attributes:
        MICRO: Smallest possible view, just key metric or icon
        MINIMIZED: Compact view showing only critical metrics
        MEDIUM: Balanced view with important details (default)
        MAXIMIZED: Full view with all available information
    """

    MICRO = "micro"
    MINIMIZED = "minimized"
    MEDIUM = "medium"
    MAXIMIZED = "maximized"

    def next(self) -> "DisplayMode":
        """Cycle to the next display mode.

        Returns:
            The next mode in the cycle: MICRO -> MINIMIZED -> MEDIUM -> MAXIMIZED -> MICRO
        """
        modes = list(DisplayMode)
        idx = (modes.index(self) + 1) % len(modes)
        return modes[idx]


def _metric_field(
    metric_type: MetricType,
    description: str = "",
    **kwargs: Any,
) -> Any:
    """Create a Pydantic Field with metric type metadata.

    Args:
        metric_type: The semantic type of this metric
        description: Human-readable description of the metric
        **kwargs: Additional Field arguments (ge, le, default, etc.)

    Returns:
        A Pydantic Field with json_schema_extra containing metric_type
    """
    extra = kwargs.pop("json_schema_extra", {})
    if isinstance(extra, dict):
        extra = {**extra, "metric_type": metric_type.value}
    else:
        extra = {"metric_type": metric_type.value}

    return Field(description=description, json_schema_extra=extra, **kwargs)


# Type aliases for common metric field patterns
# Usage: bytes_sent: Counter[int] = counter_field("Total bytes sent")
#        cpu_percent: Gauge[float] = gauge_field("CPU usage percentage", ge=0, le=100)

Counter = Annotated[int, "counter"]
"""Type alias for counter metrics (monotonically increasing integers)."""

CounterFloat = Annotated[float, "counter"]
"""Type alias for counter metrics with float precision."""

Gauge = Annotated[float, "gauge"]
"""Type alias for gauge metrics (float values that can go up/down)."""

GaugeInt = Annotated[int, "gauge"]
"""Type alias for gauge metrics with integer values."""


def counter_field(description: str = "", **kwargs: Any) -> Any:
    """Create a counter metric field.

    Counters are monotonically increasing values that only go up
    (and may reset to zero on restart).

    Args:
        description: Human-readable description
        **kwargs: Additional Field arguments

    Returns:
        Pydantic Field configured as a counter metric

    Example:
        bytes_sent: int = counter_field("Total bytes transmitted")
    """
    return _metric_field(MetricType.COUNTER, description, **kwargs)


def gauge_field(description: str = "", **kwargs: Any) -> Any:
    """Create a gauge metric field.

    Gauges represent current values that can go up and down.

    Args:
        description: Human-readable description
        **kwargs: Additional Field arguments

    Returns:
        Pydantic Field configured as a gauge metric

    Example:
        cpu_percent: float = gauge_field("Current CPU usage", ge=0, le=100)
    """
    return _metric_field(MetricType.GAUGE, description, **kwargs)


def histogram_field(description: str = "", **kwargs: Any) -> Any:
    """Create a histogram metric field.

    Histograms record observations into configurable buckets.

    Args:
        description: Human-readable description
        **kwargs: Additional Field arguments

    Returns:
        Pydantic Field configured as a histogram metric

    Example:
        latency_buckets: list[float] = histogram_field("Request latency distribution")
    """
    return _metric_field(MetricType.HISTOGRAM, description, **kwargs)


def summary_field(description: str = "", **kwargs: Any) -> Any:
    """Create a summary metric field.

    Summaries calculate streaming quantiles over a sliding window.

    Args:
        description: Human-readable description
        **kwargs: Additional Field arguments

    Returns:
        Pydantic Field configured as a summary metric

    Example:
        p99_latency: float = summary_field("99th percentile latency")
    """
    return _metric_field(MetricType.SUMMARY, description, **kwargs)


def get_metric_type(model: type[BaseModel], field_name: str) -> MetricType | None:
    """Extract the metric type from a model field.

    Args:
        model: The Pydantic model class
        field_name: Name of the field to inspect

    Returns:
        The MetricType if annotated, None otherwise

    Example:
        >>> class MyData(MetricData):
        ...     bytes_sent: int = counter_field("Total bytes")
        >>> get_metric_type(MyData, "bytes_sent")
        MetricType.COUNTER
    """
    if field_name not in model.model_fields:
        return None

    field_info: FieldInfo = model.model_fields[field_name]

    # Check json_schema_extra for metric_type (from field factories)
    extra = field_info.json_schema_extra
    if isinstance(extra, dict) and "metric_type" in extra:
        try:
            return MetricType(extra["metric_type"])
        except ValueError:
            return None

    # Check field.metadata for type alias markers (from Annotated types)
    # Pydantic extracts Annotated metadata into field_info.metadata
    if field_info.metadata:
        for item in field_info.metadata:
            if item == "counter":
                return MetricType.COUNTER
            if item == "gauge":
                return MetricType.GAUGE
            if item == "histogram":
                return MetricType.HISTOGRAM
            if item == "summary":
                return MetricType.SUMMARY

    return None


def get_all_metric_types(model: type[BaseModel]) -> dict[str, MetricType]:
    """Get metric types for all annotated fields in a model.

    Args:
        model: The Pydantic model class

    Returns:
        Dictionary mapping field names to their MetricType

    Example:
        >>> class MyData(MetricData):
        ...     bytes_sent: int = counter_field("Total bytes")
        ...     cpu_percent: float = gauge_field("CPU usage")
        >>> get_all_metric_types(MyData)
        {'bytes_sent': MetricType.COUNTER, 'cpu_percent': MetricType.GAUGE}
    """
    result: dict[str, MetricType] = {}
    for field_name in model.model_fields:
        metric_type = get_metric_type(model, field_name)
        if metric_type is not None:
            result[field_name] = metric_type
    return result


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class PluginType(str, Enum):
    """Types of plugins supported by uptop."""

    PANE = "pane"
    COLLECTOR = "collector"
    FORMATTER = "formatter"
    ACTION = "action"


class MetricData(BaseModel):
    """Base class for all metric data collected by uptop.

    All pane-specific data models should inherit from this class.
    Provides common fields like timestamp and source identification.

    Attributes:
        timestamp: When this data was collected (UTC)
        source: Identifier for the data source (e.g., plugin name)
    """

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        str_strip_whitespace=True,
    )

    timestamp: datetime = Field(default_factory=_utcnow)
    source: str = Field(default="unknown", description="Data source identifier")

    def age_seconds(self) -> float:
        """Return how old this data is in seconds."""
        return (_utcnow() - self.timestamp).total_seconds()


class PluginMetadata(BaseModel):
    """Metadata describing a registered plugin.

    This model stores information about plugins discovered and loaded by uptop.
    Used by the plugin registry to track available plugins.

    Attributes:
        name: Unique identifier for the plugin
        display_name: Human-readable name for UI display
        plugin_type: Category of plugin (pane, collector, formatter, action)
        version: Plugin version string (semver recommended)
        api_version: uptop plugin API version this plugin targets
        description: Brief description of plugin functionality
        author: Plugin author name or organization
        enabled: Whether the plugin is currently active
        entry_point: Import path for the plugin class
        config_schema: Optional JSON schema for plugin-specific config
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(..., min_length=1, max_length=128)
    plugin_type: PluginType
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+")
    api_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    description: str = Field(default="")
    author: str = Field(default="")
    enabled: bool = Field(default=True)
    entry_point: str = Field(default="", description="Import path like 'package.module:Class'")
    config_schema: dict[str, Any] | None = Field(default=None)


class SystemSnapshot(BaseModel):
    """Complete system state at a single point in time.

    Aggregates data from all active panes into a single snapshot.
    Used for CLI output and data export.

    Attributes:
        timestamp: When this snapshot was taken (UTC)
        hostname: System hostname
        panes: Dictionary mapping pane names to their MetricData
    """

    model_config = ConfigDict(extra="allow")

    timestamp: datetime = Field(default_factory=_utcnow)
    hostname: str = Field(default="")
    panes: dict[str, MetricData] = Field(default_factory=dict)

    def get_pane_data(self, pane_name: str) -> MetricData | None:
        """Get data for a specific pane by name.

        Args:
            pane_name: The name of the pane to retrieve

        Returns:
            The MetricData for that pane, or None if not present
        """
        return self.panes.get(pane_name)

    def add_pane_data(self, pane_name: str, data: MetricData) -> None:
        """Add or update data for a pane.

        Args:
            pane_name: The name of the pane
            data: The MetricData to store
        """
        self.panes[pane_name] = data
