"""In-memory store for OpenTelemetry data."""

from __future__ import annotations

import copy
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OTelEvent:
    """A single OpenTelemetry log/event entry."""
    timestamp: datetime
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    severity: str = "INFO"


@dataclass(frozen=True)
class OTelMetricSnapshot:
    """A snapshot of a single metric value."""
    metric_name: str
    value: float
    unit: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    attributes: dict[str, Any] = field(default_factory=dict)


class OTelStore:
    """Thread-safe in-memory store for OpenTelemetry data.

    Bridges the HTTP receiver (push from Claude Code) and the collector (pull on timer).
    """

    MAX_EVENTS = 500

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: dict[str, OTelMetricSnapshot] = {}
        self._events: deque[OTelEvent] = deque(maxlen=self.MAX_EVENTS)

    def ingest_metrics(self, resource_metrics: list[dict[str, Any]]) -> None:
        """Parse and store OTLP JSON metrics.

        Expected format: list of resourceMetrics objects from OTLP JSON.
        Each contains scopeMetrics -> metrics -> data points.
        """
        with self._lock:
            try:
                for rm in resource_metrics:
                    for sm in rm.get("scopeMetrics", []):
                        for metric in sm.get("metrics", []):
                            self._process_metric(metric)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Failed to parse OTLP metrics: %s", e)

    def _process_metric(self, metric: dict[str, Any]) -> None:
        """Process a single OTLP metric into the store. Must be called with lock held."""
        name = metric.get("name", "")
        unit = metric.get("unit", "")

        # Handle different metric data types (gauge, sum, histogram)
        data_points: list[dict[str, Any]] = []
        if "gauge" in metric:
            data_points = metric["gauge"].get("dataPoints", [])
        elif "sum" in metric:
            data_points = metric["sum"].get("dataPoints", [])
        elif "histogram" in metric:
            data_points = metric["histogram"].get("dataPoints", [])

        for dp in data_points:
            value = dp.get("asDouble", dp.get("asInt", 0.0))
            attrs = {}
            for attr in dp.get("attributes", []):
                key = attr.get("key", "")
                val_obj = attr.get("value", {})
                attrs[key] = (
                    val_obj.get("stringValue")
                    or val_obj.get("intValue")
                    or val_obj.get("doubleValue")
                    or val_obj.get("boolValue")
                    or ""
                )

            time_unix = dp.get("timeUnixNano", 0)
            ts = datetime.fromtimestamp(time_unix / 1e9, tz=UTC) if time_unix else datetime.now(UTC)

            snapshot = OTelMetricSnapshot(
                metric_name=name,
                value=float(value),
                unit=unit,
                timestamp=ts,
                attributes=attrs,
            )
            self._metrics[name] = snapshot

    def ingest_logs(self, resource_logs: list[dict[str, Any]]) -> None:
        """Parse and store OTLP JSON logs.

        Expected format: list of resourceLogs objects from OTLP JSON.
        Each contains scopeLogs -> logRecords.
        """
        with self._lock:
            try:
                for rl in resource_logs:
                    for sl in rl.get("scopeLogs", []):
                        for record in sl.get("logRecords", []):
                            self._process_log_record(record)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Failed to parse OTLP logs: %s", e)

    def _process_log_record(self, record: dict[str, Any]) -> None:
        """Process a single OTLP log record. Must be called with lock held."""
        time_unix = record.get("timeUnixNano", record.get("observedTimeUnixNano", 0))
        ts = datetime.fromtimestamp(time_unix / 1e9, tz=UTC) if time_unix else datetime.now(UTC)

        body = record.get("body", {})
        name = body.get("stringValue", "") if isinstance(body, dict) else str(body)

        severity = record.get("severityText", "INFO")

        attrs: dict[str, Any] = {}
        for attr in record.get("attributes", []):
            key = attr.get("key", "")
            val_obj = attr.get("value", {})
            attrs[key] = (
                val_obj.get("stringValue")
                or val_obj.get("intValue")
                or val_obj.get("doubleValue")
                or val_obj.get("boolValue")
                or ""
            )

        event = OTelEvent(
            timestamp=ts,
            name=name,
            attributes=attrs,
            severity=severity,
        )
        self._events.append(event)

    def get_snapshot(self) -> tuple[dict[str, OTelMetricSnapshot], list[OTelEvent]]:
        """Return a copy of current metrics and events.

        Returns:
            Tuple of (metrics dict copy, events list copy)
        """
        with self._lock:
            metrics_copy = copy.deepcopy(self._metrics)
            events_copy = list(self._events)
        return metrics_copy, events_copy

    def clear(self) -> None:
        """Reset all stored data."""
        with self._lock:
            self._metrics.clear()
            self._events.clear()
