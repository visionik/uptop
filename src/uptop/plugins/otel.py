"""OpenTelemetry Pane Plugin for uptop.

Receives OTLP HTTP data from Claude Code and displays telemetry
including token usage, costs, session info, and events.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from uptop.models.base import DisplayMode, MetricData, counter_field, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget

logger = logging.getLogger(__name__)


class OTelData(MetricData):
    """Data model for OpenTelemetry telemetry from Claude Code.

    Tracks session activity, token usage, costs, and recent events.
    """

    session_count: int = gauge_field("Number of active sessions", default=0, ge=0)
    total_tokens: int = counter_field("Total tokens used", default=0, ge=0)
    input_tokens: int = counter_field("Input tokens used", default=0, ge=0)
    output_tokens: int = counter_field("Output tokens used", default=0, ge=0)
    cache_read_tokens: int = counter_field("Cache read tokens", default=0, ge=0)
    cache_creation_tokens: int = counter_field("Cache creation tokens", default=0, ge=0)
    total_cost_usd: float = gauge_field("Total cost in USD", default=0.0, ge=0.0)
    lines_of_code: int = counter_field("Lines of code written", default=0, ge=0)
    num_commits: int = counter_field("Number of commits made", default=0, ge=0)
    num_prs: int = counter_field("Number of PRs created", default=0, ge=0)
    active_duration_seconds: float = gauge_field("Active session duration", default=0.0, ge=0.0)
    recent_events: list[dict[str, Any]] = Field(
        default_factory=list, description="Recent telemetry events"
    )
    event_count: int = counter_field("Total events received", default=0, ge=0)
    receiver_running: bool = Field(default=False, description="Whether the OTLP receiver is active")
    last_updated: datetime | None = Field(default=None, description="Last data update time")


# Mapping from OTLP metric names to OTelData field names
_METRIC_FIELD_MAP: dict[str, str] = {
    "session_count": "session_count",
    "total_tokens": "total_tokens",
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_tokens": "cache_read_tokens",
    "cache_creation_tokens": "cache_creation_tokens",
    "total_cost_usd": "total_cost_usd",
    "cost_usd": "total_cost_usd",
    "lines_of_code": "lines_of_code",
    "num_commits": "num_commits",
    "num_prs": "num_prs",
    "active_duration_seconds": "active_duration_seconds",
    "active_duration": "active_duration_seconds",
}


class OTelPane(PanePlugin):
    """OpenTelemetry pane plugin for monitoring Claude Code telemetry."""

    name = "otel"
    display_name = "OpenTelemetry"
    version = "0.1.0"
    description = "Claude Code telemetry monitor"
    default_refresh_interval = 2.0

    def __init__(self) -> None:
        super().__init__()
        self._store: Any = None  # Lazy init
        self._receiver: Any = None  # Lazy init
        self._receiver_started: bool = False

    def _ensure_store(self) -> Any:
        """Lazily initialize the OTelStore."""
        if self._store is None:
            from uptop.otel.store import OTelStore
            self._store = OTelStore()
        return self._store

    async def _ensure_receiver(self) -> None:
        """Lazily start the OTLP HTTP receiver."""
        if not self._receiver_started:
            from uptop.otel.receiver import OTelReceiver
            store = self._ensure_store()
            host = self.config.get("host", "127.0.0.1")
            port = self.config.get("port", 4318)
            self._receiver = OTelReceiver(store=store, host=host, port=port)
            try:
                await self._receiver.start()
                self._receiver_started = True
                logger.info("OTel receiver started on %s:%d", host, port)
            except OSError as e:
                logger.warning("Failed to start OTel receiver: %s", e)

    async def collect_data(self) -> OTelData:
        """Collect current telemetry data from the store."""
        await self._ensure_receiver()
        store = self._ensure_store()

        metrics, events = store.get_snapshot()

        # Map metrics to OTelData fields
        field_values: dict[str, Any] = {}
        for metric_name, snapshot in metrics.items():
            field_name = _METRIC_FIELD_MAP.get(metric_name)
            if field_name:
                value = snapshot.value
                # Convert to int for integer fields
                if field_name in (
                    "session_count", "total_tokens", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_creation_tokens", "lines_of_code",
                    "num_commits", "num_prs", "event_count",
                ):
                    value = int(value)
                field_values[field_name] = value

        # Format recent events for display (last 50)
        recent = []
        for event in events[-50:]:
            recent.append({
                "timestamp": event.timestamp.isoformat(),
                "name": event.name,
                "severity": event.severity,
                "attributes": event.attributes,
            })

        return OTelData(
            source="otel",
            receiver_running=self._receiver_started,
            event_count=len(events),
            recent_events=recent,
            last_updated=datetime.now(UTC) if (metrics or events) else None,
            **field_values,
        )

    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> "Widget":
        """Render the OTel widget."""
        from uptop.tui.panes.otel_widget import OTelWidget
        return OTelWidget(data=data if isinstance(data, OTelData) else None, id=f"pane-{self.name}")

    def get_schema(self) -> type[BaseModel]:
        """Return the data schema."""
        return OTelData

    def get_default_config(self) -> dict[str, Any]:
        """Get default configuration."""
        return {
            "host": "127.0.0.1",
            "port": 4318,
            "refresh_interval": 2.0,
        }

    def shutdown(self) -> None:
        """Clean up receiver on shutdown."""
        # Note: receiver cleanup is async, handled via event loop if available
        super().shutdown()
