"""Tests for the OpenTelemetry plugin."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from uptop.models.base import DisplayMode, MetricType, get_metric_type
from uptop.plugins.otel import OTelData, OTelPane, _METRIC_FIELD_MAP


class TestOTelData:
    """Tests for the OTelData model."""

    def test_default_values(self) -> None:
        data = OTelData()
        assert data.session_count == 0
        assert data.total_tokens == 0
        assert data.input_tokens == 0
        assert data.output_tokens == 0
        assert data.cache_read_tokens == 0
        assert data.cache_creation_tokens == 0
        assert data.total_cost_usd == 0.0
        assert data.lines_of_code == 0
        assert data.num_commits == 0
        assert data.num_prs == 0
        assert data.active_duration_seconds == 0.0
        assert data.recent_events == []
        assert data.event_count == 0
        assert data.receiver_running is False
        assert data.last_updated is None

    def test_with_values(self) -> None:
        data = OTelData(
            total_tokens=5000,
            input_tokens=3000,
            output_tokens=2000,
            total_cost_usd=0.42,
            session_count=2,
        )
        assert data.total_tokens == 5000
        assert data.total_cost_usd == 0.42

    def test_metric_type_gauge_fields(self) -> None:
        assert get_metric_type(OTelData, "session_count") == MetricType.GAUGE
        assert get_metric_type(OTelData, "total_cost_usd") == MetricType.GAUGE
        assert get_metric_type(OTelData, "active_duration_seconds") == MetricType.GAUGE

    def test_metric_type_counter_fields(self) -> None:
        assert get_metric_type(OTelData, "total_tokens") == MetricType.COUNTER
        assert get_metric_type(OTelData, "input_tokens") == MetricType.COUNTER
        assert get_metric_type(OTelData, "output_tokens") == MetricType.COUNTER
        assert get_metric_type(OTelData, "lines_of_code") == MetricType.COUNTER
        assert get_metric_type(OTelData, "event_count") == MetricType.COUNTER

    def test_inherits_metric_data(self) -> None:
        data = OTelData(source="otel")
        assert data.source == "otel"
        assert data.timestamp is not None
        assert data.age_seconds() >= 0


class TestOTelPane:
    """Tests for the OTelPane plugin."""

    @pytest.fixture
    def pane(self) -> OTelPane:
        return OTelPane()

    def test_metadata(self, pane: OTelPane) -> None:
        assert pane.name == "otel"
        assert pane.display_name == "OpenTelemetry"
        assert pane.description == "Claude Code telemetry monitor"
        assert pane.default_refresh_interval == 2.0

    def test_get_schema(self, pane: OTelPane) -> None:
        schema = pane.get_schema()
        assert schema is OTelData
        assert issubclass(schema, BaseModel)

    def test_get_default_config(self, pane: OTelPane) -> None:
        config = pane.get_default_config()
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 4318
        assert config["refresh_interval"] == 2.0

    def test_render_tui_returns_widget(self, pane: OTelPane) -> None:
        data = OTelData()
        widget = pane.render_tui(data, mode=DisplayMode.MEDIUM)
        from uptop.tui.panes.otel_widget import OTelWidget
        assert isinstance(widget, OTelWidget)

    def test_render_tui_with_none_data(self, pane: OTelPane) -> None:
        """render_tui should handle non-OTelData gracefully."""
        from uptop.models.base import MetricData
        data = MetricData()
        widget = pane.render_tui(data)
        from uptop.tui.panes.otel_widget import OTelWidget
        assert isinstance(widget, OTelWidget)

    def test_lazy_store_initialization(self, pane: OTelPane) -> None:
        assert pane._store is None
        store = pane._ensure_store()
        assert store is not None
        # Second call returns same instance
        assert pane._ensure_store() is store

    @pytest.mark.asyncio
    async def test_collect_data_empty_store(self, pane: OTelPane) -> None:
        """Test collecting from an empty store returns defaults."""
        # Mock receiver to avoid port binding
        with patch.object(pane, '_ensure_receiver', new_callable=AsyncMock):
            pane._ensure_store()
            data = await pane.collect_data()
            assert isinstance(data, OTelData)
            assert data.total_tokens == 0
            assert data.total_cost_usd == 0.0
            assert data.recent_events == []

    @pytest.mark.asyncio
    async def test_collect_data_with_metrics(self, pane: OTelPane) -> None:
        """Test collecting maps metrics to OTelData fields."""
        with patch.object(pane, '_ensure_receiver', new_callable=AsyncMock):
            store = pane._ensure_store()
            store.ingest_metrics([
                {
                    "scopeMetrics": [
                        {
                            "metrics": [
                                {
                                    "name": "total_tokens",
                                    "gauge": {
                                        "dataPoints": [
                                            {"asInt": 5000, "timeUnixNano": 0, "attributes": []}
                                        ]
                                    },
                                },
                                {
                                    "name": "total_cost_usd",
                                    "gauge": {
                                        "dataPoints": [
                                            {"asDouble": 1.23, "timeUnixNano": 0, "attributes": []}
                                        ]
                                    },
                                },
                            ]
                        }
                    ]
                }
            ])

            data = await pane.collect_data()
            assert data.total_tokens == 5000
            assert data.total_cost_usd == 1.23

    @pytest.mark.asyncio
    async def test_collect_data_with_events(self, pane: OTelPane) -> None:
        """Test collecting includes recent events."""
        with patch.object(pane, '_ensure_receiver', new_callable=AsyncMock):
            store = pane._ensure_store()
            store.ingest_logs([
                {
                    "scopeLogs": [
                        {
                            "logRecords": [
                                {
                                    "timeUnixNano": 1700000000000000000,
                                    "body": {"stringValue": "tool_use"},
                                    "severityText": "INFO",
                                    "attributes": [],
                                }
                            ]
                        }
                    ]
                }
            ])

            data = await pane.collect_data()
            assert data.event_count == 1
            assert len(data.recent_events) == 1
            assert data.recent_events[0]["name"] == "tool_use"

    @pytest.mark.asyncio
    async def test_lazy_receiver_not_started_until_collect(self, pane: OTelPane) -> None:
        assert pane._receiver_started is False
        assert pane._receiver is None

    def test_plugin_type(self) -> None:
        from uptop.models.base import PluginType
        assert OTelPane.get_plugin_type() == PluginType.PANE

    def test_get_metadata(self) -> None:
        meta = OTelPane.get_metadata()
        assert meta.name == "otel"
        assert meta.display_name == "OpenTelemetry"

    def test_shutdown(self, pane: OTelPane) -> None:
        pane.initialize()
        assert pane._initialized is True
        pane.shutdown()
        assert pane._initialized is False
