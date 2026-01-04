"""Prometheus formatter plugin for uptop CLI output.

This module provides Prometheus text format output for CLI mode,
converting SystemSnapshot data to Prometheus exposition format
for scraping by Prometheus or compatible tools.

Format specification: https://prometheus.io/docs/instrumenting/exposition_formats/
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from uptop.models.base import MetricData, MetricType, PluginType, get_metric_type
from uptop.plugin_api.base import FormatterPlugin


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


def _sanitize_metric_name(name: str) -> str:
    """Sanitize a metric name to comply with Prometheus naming conventions.

    Prometheus metric names must match [a-zA-Z_:][a-zA-Z0-9_:]*

    Args:
        name: The raw metric name

    Returns:
        Sanitized metric name
    """
    # Replace invalid characters with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


def _sanitize_label_value(value: str) -> str:
    """Sanitize a label value for Prometheus format.

    Label values can contain any unicode characters but need escaping
    for backslash, newline, and double quotes.

    Args:
        value: The raw label value

    Returns:
        Escaped label value
    """
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: dict[str, str]) -> str:
    """Format labels as Prometheus label string.

    Args:
        labels: Dictionary of label name -> value

    Returns:
        Formatted label string like {foo="bar",baz="qux"}
    """
    if not labels:
        return ""
    pairs = [f'{k}="{_sanitize_label_value(str(v))}"' for k, v in labels.items()]
    return "{" + ",".join(pairs) + "}"


class PrometheusFormatter(FormatterPlugin):
    """Prometheus text format formatter.

    Converts system snapshot data to Prometheus exposition format,
    suitable for scraping by Prometheus or compatible monitoring systems.

    Class Attributes:
        name: Plugin identifier
        display_name: Human-readable name
        format_name: Format identifier for CLI selection
        cli_flag: CLI flag to select this format
        file_extension: Default file extension for output
    """

    name: str = "prometheus"
    display_name: str = "Prometheus Formatter"
    format_name: str = "prometheus"
    cli_flag: str = "--prometheus"
    file_extension: str = ".prom"
    version: str = "0.1.0"
    description: str = "Format system metrics in Prometheus text format"
    author: str = "uptop"

    def __init__(self) -> None:
        """Initialize the Prometheus formatter."""
        super().__init__()
        self._prefix: str = "uptop"
        self._include_help: bool = True
        self._include_type: bool = True

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize formatter with configuration.

        Args:
            config: Formatter configuration
                - prefix: Metric name prefix (default: "uptop")
                - include_help: Include HELP comments (default: True)
                - include_type: Include TYPE comments (default: True)
        """
        super().initialize(config)
        if config:
            self._prefix = config.get("prefix", "uptop")
            self._include_help = config.get("include_help", True)
            self._include_type = config.get("include_type", True)

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return FORMATTER plugin type."""
        return PluginType.FORMATTER

    def format(self, data: dict[str, Any]) -> str:
        """Format system data as Prometheus text format.

        Args:
            data: Dictionary containing SystemSnapshot-like data.
                  Expected keys:
                  - "panes": dict[str, MetricData]
                  - "timestamp": datetime (optional)
                  - "hostname": str (optional)

        Returns:
            Prometheus exposition format string

        Example output:
            # HELP uptop_cpu_usage_percent CPU usage percentage per core
            # TYPE uptop_cpu_usage_percent gauge
            uptop_cpu_usage_percent{core="0"} 45.2
            uptop_cpu_usage_percent{core="1"} 52.1
        """
        lines: list[str] = []
        timestamp = data.get("timestamp")
        if timestamp is None:
            timestamp = _utcnow()

        # Convert timestamp to milliseconds for Prometheus
        if isinstance(timestamp, datetime):
            timestamp_ms = int(timestamp.timestamp() * 1000)
        else:
            timestamp_ms = None

        hostname = data.get("hostname", "")
        base_labels = {"host": hostname} if hostname else {}

        panes = data.get("panes", {})

        for pane_name, pane_data in panes.items():
            pane_lines = self._format_pane(pane_name, pane_data, base_labels, timestamp_ms)
            lines.extend(pane_lines)

        return "\n".join(lines) + "\n" if lines else ""

    def _format_pane(
        self,
        pane_name: str,
        pane_data: MetricData | dict[str, Any],
        base_labels: dict[str, str],
        timestamp_ms: int | None = None,
    ) -> list[str]:
        """Format a single pane's data as Prometheus metrics.

        Args:
            pane_name: Name of the pane (e.g., "cpu", "memory")
            pane_data: The pane's MetricData or dict
            base_labels: Labels to add to all metrics
            timestamp_ms: Optional timestamp in milliseconds

        Returns:
            List of Prometheus metric lines
        """
        lines: list[str] = []

        if isinstance(pane_data, MetricData):
            data_dict = pane_data.model_dump()
            schema_class = type(pane_data)
        elif isinstance(pane_data, dict):
            data_dict = pane_data
            schema_class = None
        else:
            return lines

        # Process each field in the pane data
        lines.extend(
            self._format_dict(
                prefix=f"{self._prefix}_{pane_name}",
                data=data_dict,
                base_labels=base_labels,
                schema_class=schema_class,
                timestamp_ms=timestamp_ms,
            )
        )

        return lines

    def _format_dict(
        self,
        prefix: str,
        data: dict[str, Any],
        base_labels: dict[str, str],
        schema_class: type[BaseModel] | None = None,
        timestamp_ms: int | None = None,
    ) -> list[str]:
        """Format a dictionary of values as Prometheus metrics.

        Args:
            prefix: Metric name prefix
            data: Dictionary of field name -> value
            base_labels: Labels to add to all metrics
            schema_class: Optional Pydantic model class for type metadata
            timestamp_ms: Optional timestamp in milliseconds

        Returns:
            List of Prometheus metric lines
        """
        lines: list[str] = []

        for field_name, value in data.items():
            # Skip metadata fields
            if field_name in ("timestamp", "source"):
                continue

            metric_name = _sanitize_metric_name(f"{prefix}_{field_name}")

            # Get metric type from schema if available
            metric_type: MetricType | None = None
            if schema_class is not None:
                metric_type = get_metric_type(schema_class, field_name)

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                # Scalar numeric value
                lines.extend(
                    self._format_scalar(
                        metric_name, value, base_labels, metric_type, timestamp_ms
                    )
                )

            elif isinstance(value, list):
                # List of items (e.g., CPU cores, interfaces)
                lines.extend(
                    self._format_list(
                        metric_name, value, base_labels, timestamp_ms
                    )
                )

            elif isinstance(value, dict):
                # Nested object
                lines.extend(
                    self._format_dict(
                        metric_name, value, base_labels, None, timestamp_ms
                    )
                )

            elif isinstance(value, BaseModel):
                # Nested Pydantic model
                lines.extend(
                    self._format_dict(
                        metric_name,
                        value.model_dump(),
                        base_labels,
                        type(value),
                        timestamp_ms,
                    )
                )

        return lines

    def _format_scalar(
        self,
        metric_name: str,
        value: int | float,
        labels: dict[str, str],
        metric_type: MetricType | None = None,
        timestamp_ms: int | None = None,
    ) -> list[str]:
        """Format a scalar metric value.

        Args:
            metric_name: Full metric name
            value: The metric value
            labels: Labels for this metric
            metric_type: Optional Prometheus metric type
            timestamp_ms: Optional timestamp in milliseconds

        Returns:
            List of lines including HELP, TYPE, and value
        """
        lines: list[str] = []

        # Add HELP comment if configured
        if self._include_help:
            lines.append(f"# HELP {metric_name} {metric_name}")

        # Add TYPE comment if configured and known
        if self._include_type and metric_type:
            prom_type = "gauge" if metric_type == MetricType.GAUGE else "counter"
            lines.append(f"# TYPE {metric_name} {prom_type}")

        # Format the metric line
        label_str = _format_labels(labels)
        if timestamp_ms is not None:
            lines.append(f"{metric_name}{label_str} {value} {timestamp_ms}")
        else:
            lines.append(f"{metric_name}{label_str} {value}")

        return lines

    def _format_list(
        self,
        metric_name: str,
        values: list[Any],
        base_labels: dict[str, str],
        timestamp_ms: int | None = None,
    ) -> list[str]:
        """Format a list of items as labeled metrics.

        Args:
            metric_name: Base metric name
            values: List of items to format
            base_labels: Labels to add to all metrics
            timestamp_ms: Optional timestamp in milliseconds

        Returns:
            List of Prometheus metric lines
        """
        lines: list[str] = []

        for idx, item in enumerate(values):
            if isinstance(item, dict):
                # Get identifier for this item (e.g., core id, interface name)
                item_id = item.get("id", item.get("name", str(idx)))
                item_labels = {**base_labels, "id": str(item_id)}

                for field_name, value in item.items():
                    if field_name in ("id", "name", "timestamp", "source"):
                        continue

                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        field_metric = _sanitize_metric_name(f"{metric_name}_{field_name}")
                        label_str = _format_labels(item_labels)
                        if timestamp_ms is not None:
                            lines.append(f"{field_metric}{label_str} {value} {timestamp_ms}")
                        else:
                            lines.append(f"{field_metric}{label_str} {value}")

            elif isinstance(item, BaseModel):
                # Pydantic model in list
                item_dict = item.model_dump()
                item_id = item_dict.get("id", item_dict.get("name", str(idx)))
                item_labels = {**base_labels, "id": str(item_id)}

                for field_name, value in item_dict.items():
                    if field_name in ("id", "name", "timestamp", "source"):
                        continue

                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        field_metric = _sanitize_metric_name(f"{metric_name}_{field_name}")
                        label_str = _format_labels(item_labels)
                        if timestamp_ms is not None:
                            lines.append(f"{field_metric}{label_str} {value} {timestamp_ms}")
                        else:
                            lines.append(f"{field_metric}{label_str} {value}")

            elif isinstance(item, (int, float)) and not isinstance(item, bool):
                # Simple numeric list
                item_labels = {**base_labels, "index": str(idx)}
                label_str = _format_labels(item_labels)
                if timestamp_ms is not None:
                    lines.append(f"{metric_name}{label_str} {item} {timestamp_ms}")
                else:
                    lines.append(f"{metric_name}{label_str} {item}")

        return lines

    def get_ai_help_docs(self) -> str:
        """Return markdown documentation for --ai-help output.

        Returns:
            Markdown-formatted string describing the plugin.
        """
        return """## Prometheus Formatter

The Prometheus Formatter outputs metrics in Prometheus text exposition format.

### Usage
```bash
uptop --prometheus           # Output metrics in Prometheus format
uptop --prometheus --once    # Single snapshot, exit immediately
```

### Configuration Options
- `prefix`: Metric name prefix (default: "uptop")
- `include_help`: Include HELP comments (default: true)
- `include_type`: Include TYPE comments (default: true)

### Output Format
```
# HELP uptop_cpu_cores_usage_percent CPU usage percentage per core
# TYPE uptop_cpu_cores_usage_percent gauge
uptop_cpu_cores_usage_percent{id="0"} 45.2
uptop_cpu_cores_usage_percent{id="1"} 52.1
# HELP uptop_memory_virtual_percent Memory usage percentage
# TYPE uptop_memory_virtual_percent gauge
uptop_memory_virtual_percent 78.5
```

### Notes
- All metric names are prefixed with "uptop_" by default
- Metric names are sanitized to comply with Prometheus naming conventions
- Labels are used for multi-instance metrics (cores, interfaces, etc.)
- Counter and gauge types are detected from Pydantic field metadata
"""
