"""Lightweight OTLP HTTP receiver for OpenTelemetry data."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from uptop.otel.store import OTelStore

logger = logging.getLogger(__name__)


class OTelReceiver:
    """HTTP server accepting OTLP JSON data from Claude Code.

    Listens on the configured host/port for OTLP HTTP exports and
    stores the data in an OTelStore for later consumption.
    """

    def __init__(
        self,
        store: OTelStore,
        host: str = "127.0.0.1",
        port: int = 4318,
    ) -> None:
        self.store = store
        self.host = host
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    def _create_app(self) -> web.Application:
        """Create the aiohttp application with routes."""
        app = web.Application()
        app.router.add_post("/v1/metrics", self._handle_metrics)
        app.router.add_post("/v1/logs", self._handle_logs)
        return app

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle POST /v1/metrics with OTLP JSON payload."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
            )

        resource_metrics = data.get("resourceMetrics", [])
        self.store.ingest_metrics(resource_metrics)
        return web.json_response({})

    async def _handle_logs(self, request: web.Request) -> web.Response:
        """Handle POST /v1/logs with OTLP JSON payload."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
            )

        resource_logs = data.get("resourceLogs", [])
        self.store.ingest_logs(resource_logs)
        return web.json_response({})

    async def start(self) -> None:
        """Start the HTTP server."""
        self._app = self._create_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info("OTel receiver listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Gracefully shut down the HTTP server."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            self._app = None
            logger.info("OTel receiver stopped")
