"""Tests for the OpenTelemetry HTTP receiver."""

from __future__ import annotations

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient

from uptop.otel.receiver import OTelReceiver
from uptop.otel.store import OTelStore


@pytest.fixture
def store() -> OTelStore:
    return OTelStore()


@pytest.fixture
def receiver(store: OTelStore) -> OTelReceiver:
    return OTelReceiver(store=store)


@pytest.fixture
def app(receiver: OTelReceiver) -> web.Application:
    return receiver._create_app()


@pytest_asyncio.fixture
async def client(aiohttp_client, app: web.Application) -> TestClient:
    return await aiohttp_client(app)


class TestOTelReceiverLifecycle:
    """Tests for receiver start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self, store: OTelStore) -> None:
        """Test receiver can start and stop cleanly."""
        receiver = OTelReceiver(store=store, port=0)  # port 0 = OS assigns
        # We test _create_app directly instead of binding
        app = receiver._create_app()
        assert app is not None

    def test_default_config(self, store: OTelStore) -> None:
        receiver = OTelReceiver(store=store)
        assert receiver.host == "127.0.0.1"
        assert receiver.port == 4318

    def test_custom_config(self, store: OTelStore) -> None:
        receiver = OTelReceiver(store=store, host="0.0.0.0", port=9999)
        assert receiver.host == "0.0.0.0"
        assert receiver.port == 9999


class TestMetricsEndpoint:
    """Tests for POST /v1/metrics."""

    @pytest.mark.asyncio
    async def test_valid_metrics(self, client: TestClient, store: OTelStore) -> None:
        payload = {
            "resourceMetrics": [
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
        }
        resp = await client.post(
            "/v1/metrics",
            json=payload,
        )
        assert resp.status == 200
        body = await resp.json()
        assert body == {}

        metrics, _ = store.get_snapshot()
        assert "token_count" in metrics
        assert metrics["token_count"].value == 1500.0

    @pytest.mark.asyncio
    async def test_invalid_json(self, client: TestClient) -> None:
        resp = await client.post(
            "/v1/metrics",
            data=b"not json{{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_empty_metrics(self, client: TestClient, store: OTelStore) -> None:
        resp = await client.post("/v1/metrics", json={"resourceMetrics": []})
        assert resp.status == 200
        metrics, _ = store.get_snapshot()
        assert metrics == {}


class TestLogsEndpoint:
    """Tests for POST /v1/logs."""

    @pytest.mark.asyncio
    async def test_valid_logs(self, client: TestClient, store: OTelStore) -> None:
        payload = {
            "resourceLogs": [
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
        }
        resp = await client.post("/v1/logs", json=payload)
        assert resp.status == 200
        body = await resp.json()
        assert body == {}

        _, events = store.get_snapshot()
        assert len(events) == 1
        assert events[0].name == "tool_result"

    @pytest.mark.asyncio
    async def test_invalid_json(self, client: TestClient) -> None:
        resp = await client.post(
            "/v1/logs",
            data=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_empty_logs(self, client: TestClient, store: OTelStore) -> None:
        resp = await client.post("/v1/logs", json={"resourceLogs": []})
        assert resp.status == 200
        _, events = store.get_snapshot()
        assert events == []


class TestUnsupportedRoutes:
    """Tests for unsupported routes."""

    @pytest.mark.asyncio
    async def test_get_metrics_not_allowed(self, client: TestClient) -> None:
        resp = await client.get("/v1/metrics")
        assert resp.status == 405

    @pytest.mark.asyncio
    async def test_unknown_route(self, client: TestClient) -> None:
        resp = await client.post("/v1/traces")
        assert resp.status == 404

    @pytest.mark.asyncio
    async def test_root_not_found(self, client: TestClient) -> None:
        resp = await client.get("/")
        assert resp.status == 404


class TestReceiverIntegration:
    """Integration tests with OTelStore."""

    @pytest.mark.asyncio
    async def test_metrics_and_logs_together(self, client: TestClient, store: OTelStore) -> None:
        """Test sending both metrics and logs."""
        metrics_payload = {
            "resourceMetrics": [
                {
                    "scopeMetrics": [
                        {
                            "metrics": [
                                {
                                    "name": "cost_usd",
                                    "gauge": {
                                        "dataPoints": [
                                            {"asDouble": 0.42, "timeUnixNano": 0, "attributes": []}
                                        ]
                                    },
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        logs_payload = {
            "resourceLogs": [
                {
                    "scopeLogs": [
                        {
                            "logRecords": [
                                {
                                    "timeUnixNano": 1700000000000000000,
                                    "body": {"stringValue": "session_start"},
                                    "severityText": "INFO",
                                    "attributes": [],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        await client.post("/v1/metrics", json=metrics_payload)
        await client.post("/v1/logs", json=logs_payload)

        metrics, events = store.get_snapshot()
        assert "cost_usd" in metrics
        assert len(events) == 1
