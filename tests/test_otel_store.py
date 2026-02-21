"""Tests for the OpenTelemetry store."""

import threading
import time
from datetime import UTC, datetime

import pytest

from uptop.otel.store import OTelEvent, OTelMetricSnapshot, OTelStore


class TestOTelEvent:
    """Tests for the OTelEvent dataclass."""

    def test_creation_with_defaults(self) -> None:
        event = OTelEvent(timestamp=datetime.now(UTC), name="test_event")
        assert event.name == "test_event"
        assert event.attributes == {}
        assert event.severity == "INFO"

    def test_creation_with_all_fields(self) -> None:
        ts = datetime.now(UTC)
        event = OTelEvent(
            timestamp=ts,
            name="api_request",
            attributes={"model": "claude-3", "tokens": 100},
            severity="WARN",
        )
        assert event.timestamp == ts
        assert event.name == "api_request"
        assert event.attributes["model"] == "claude-3"
        assert event.severity == "WARN"

    def test_frozen(self) -> None:
        event = OTelEvent(timestamp=datetime.now(UTC), name="test")
        with pytest.raises(AttributeError):
            event.name = "changed"


class TestOTelMetricSnapshot:
    """Tests for the OTelMetricSnapshot dataclass."""

    def test_creation_with_defaults(self) -> None:
        snap = OTelMetricSnapshot(metric_name="tokens", value=42.0)
        assert snap.metric_name == "tokens"
        assert snap.value == 42.0
        assert snap.unit == ""
        assert snap.attributes == {}

    def test_creation_with_all_fields(self) -> None:
        ts = datetime.now(UTC)
        snap = OTelMetricSnapshot(
            metric_name="cost_usd",
            value=1.23,
            unit="USD",
            timestamp=ts,
            attributes={"session": "abc"},
        )
        assert snap.value == 1.23
        assert snap.unit == "USD"
        assert snap.timestamp == ts

    def test_frozen(self) -> None:
        snap = OTelMetricSnapshot(metric_name="test", value=1.0)
        with pytest.raises(AttributeError):
            snap.value = 2.0


class TestOTelStore:
    """Tests for the OTelStore class."""

    @pytest.fixture
    def store(self) -> OTelStore:
        return OTelStore()

    def test_initialization_empty(self, store: OTelStore) -> None:
        metrics, events = store.get_snapshot()
        assert metrics == {}
        assert events == []

    def test_ingest_metrics_single(self, store: OTelStore) -> None:
        resource_metrics = [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "token_count",
                                "unit": "tokens",
                                "sum": {
                                    "dataPoints": [
                                        {
                                            "asInt": 1500,
                                            "timeUnixNano": 1700000000000000000,
                                            "attributes": [],
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        ]
        store.ingest_metrics(resource_metrics)
        metrics, _ = store.get_snapshot()
        assert "token_count" in metrics
        assert metrics["token_count"].value == 1500.0
        assert metrics["token_count"].unit == "tokens"

    def test_ingest_metrics_multiple(self, store: OTelStore) -> None:
        resource_metrics = [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "input_tokens",
                                "gauge": {
                                    "dataPoints": [
                                        {"asInt": 500, "timeUnixNano": 0, "attributes": []}
                                    ]
                                },
                            },
                            {
                                "name": "output_tokens",
                                "gauge": {
                                    "dataPoints": [
                                        {"asDouble": 300.0, "timeUnixNano": 0, "attributes": []}
                                    ]
                                },
                            },
                        ]
                    }
                ]
            }
        ]
        store.ingest_metrics(resource_metrics)
        metrics, _ = store.get_snapshot()
        assert len(metrics) == 2
        assert metrics["input_tokens"].value == 500.0
        assert metrics["output_tokens"].value == 300.0

    def test_ingest_metrics_with_attributes(self, store: OTelStore) -> None:
        resource_metrics = [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "cost",
                                "gauge": {
                                    "dataPoints": [
                                        {
                                            "asDouble": 0.42,
                                            "timeUnixNano": 0,
                                            "attributes": [
                                                {
                                                    "key": "model",
                                                    "value": {"stringValue": "claude-3"},
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        ]
        store.ingest_metrics(resource_metrics)
        metrics, _ = store.get_snapshot()
        assert metrics["cost"].attributes["model"] == "claude-3"

    def test_ingest_metrics_malformed_data(self, store: OTelStore) -> None:
        store.ingest_metrics([{"bad": "data"}])
        metrics, _ = store.get_snapshot()
        assert metrics == {}

    def test_ingest_metrics_empty_list(self, store: OTelStore) -> None:
        store.ingest_metrics([])
        metrics, _ = store.get_snapshot()
        assert metrics == {}

    def test_ingest_logs_single(self, store: OTelStore) -> None:
        resource_logs = [
            {
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": 1700000000000000000,
                                "body": {"stringValue": "tool_result"},
                                "severityText": "INFO",
                                "attributes": [
                                    {"key": "tool", "value": {"stringValue": "bash"}},
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
        store.ingest_logs(resource_logs)
        _, events = store.get_snapshot()
        assert len(events) == 1
        assert events[0].name == "tool_result"
        assert events[0].attributes["tool"] == "bash"
        assert events[0].severity == "INFO"

    def test_ingest_logs_multiple(self, store: OTelStore) -> None:
        resource_logs = [
            {
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": 1700000000000000000,
                                "body": {"stringValue": "event1"},
                                "severityText": "INFO",
                                "attributes": [],
                            },
                            {
                                "timeUnixNano": 1700000001000000000,
                                "body": {"stringValue": "event2"},
                                "severityText": "WARN",
                                "attributes": [],
                            },
                        ]
                    }
                ]
            }
        ]
        store.ingest_logs(resource_logs)
        _, events = store.get_snapshot()
        assert len(events) == 2

    def test_ingest_logs_malformed_data(self, store: OTelStore) -> None:
        store.ingest_logs([{"bad": "data"}])
        _, events = store.get_snapshot()
        assert events == []

    def test_get_snapshot_returns_copies(self, store: OTelStore) -> None:
        resource_metrics = [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "test",
                                "gauge": {
                                    "dataPoints": [
                                        {"asDouble": 1.0, "timeUnixNano": 0, "attributes": []}
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        ]
        store.ingest_metrics(resource_metrics)

        metrics1, events1 = store.get_snapshot()
        metrics2, events2 = store.get_snapshot()

        # Modifying one copy shouldn't affect the other
        metrics1.pop("test", None)
        metrics3, _ = store.get_snapshot()
        assert "test" in metrics3

    def test_event_ring_buffer_bounds(self, store: OTelStore) -> None:
        """Test that events deque respects MAX_EVENTS limit."""
        for i in range(600):
            resource_logs = [
                {
                    "scopeLogs": [
                        {
                            "logRecords": [
                                {
                                    "timeUnixNano": 1700000000000000000 + i,
                                    "body": {"stringValue": f"event_{i}"},
                                    "severityText": "INFO",
                                    "attributes": [],
                                }
                            ]
                        }
                    ]
                }
            ]
            store.ingest_logs(resource_logs)

        _, events = store.get_snapshot()
        assert len(events) == 500
        # Oldest events should have been dropped, newest kept
        assert events[0].name == "event_100"
        assert events[-1].name == "event_599"

    def test_clear_resets_all_data(self, store: OTelStore) -> None:
        resource_metrics = [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "test",
                                "gauge": {
                                    "dataPoints": [
                                        {"asDouble": 1.0, "timeUnixNano": 0, "attributes": []}
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        ]
        resource_logs = [
            {
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": 1700000000000000000,
                                "body": {"stringValue": "test"},
                                "severityText": "INFO",
                                "attributes": [],
                            }
                        ]
                    }
                ]
            }
        ]
        store.ingest_metrics(resource_metrics)
        store.ingest_logs(resource_logs)

        store.clear()
        metrics, events = store.get_snapshot()
        assert metrics == {}
        assert events == []

    def test_thread_safety_concurrent_writes(self, store: OTelStore) -> None:
        """Test concurrent access from multiple threads."""
        errors: list[Exception] = []

        def write_metrics(n: int) -> None:
            try:
                for i in range(50):
                    store.ingest_metrics([
                        {
                            "scopeMetrics": [
                                {
                                    "metrics": [
                                        {
                                            "name": f"metric_t{n}_{i}",
                                            "gauge": {
                                                "dataPoints": [
                                                    {"asDouble": float(i), "timeUnixNano": 0, "attributes": []}
                                                ]
                                            },
                                        }
                                    ]
                                }
                            ]
                        }
                    ])
            except Exception as e:
                errors.append(e)

        def write_logs(n: int) -> None:
            try:
                for i in range(50):
                    store.ingest_logs([
                        {
                            "scopeLogs": [
                                {
                                    "logRecords": [
                                        {
                                            "timeUnixNano": 1700000000000000000 + i,
                                            "body": {"stringValue": f"event_t{n}_{i}"},
                                            "severityText": "INFO",
                                            "attributes": [],
                                        }
                                    ]
                                }
                            ]
                        }
                    ])
            except Exception as e:
                errors.append(e)

        threads = []
        for n in range(4):
            threads.append(threading.Thread(target=write_metrics, args=(n,)))
            threads.append(threading.Thread(target=write_logs, args=(n,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        metrics, events = store.get_snapshot()
        assert len(metrics) > 0
        assert len(events) > 0

    def test_metric_overwrite_latest_wins(self, store: OTelStore) -> None:
        """Test that ingesting a metric with the same name overwrites the previous value."""
        for val in [1.0, 2.0, 3.0]:
            store.ingest_metrics([
                {
                    "scopeMetrics": [
                        {
                            "metrics": [
                                {
                                    "name": "same_metric",
                                    "gauge": {
                                        "dataPoints": [
                                            {"asDouble": val, "timeUnixNano": 0, "attributes": []}
                                        ]
                                    },
                                }
                            ]
                        }
                    ]
                }
            ])

        metrics, _ = store.get_snapshot()
        assert metrics["same_metric"].value == 3.0

    def test_ingest_histogram_metric(self, store: OTelStore) -> None:
        """Test ingesting histogram-type metrics."""
        resource_metrics = [
            {
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": "latency",
                                "histogram": {
                                    "dataPoints": [
                                        {"asDouble": 42.5, "timeUnixNano": 0, "attributes": []}
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        ]
        store.ingest_metrics(resource_metrics)
        metrics, _ = store.get_snapshot()
        assert "latency" in metrics
