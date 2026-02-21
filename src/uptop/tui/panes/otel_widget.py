"""OpenTelemetry Widget for uptop TUI.

Displays Claude Code telemetry data including token usage, costs,
session activity, and recent events.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from uptop.models.base import DisplayMode

if TYPE_CHECKING:
    from uptop.plugins.otel import OTelData


def format_tokens(count: int) -> str:
    """Format token count for display."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def format_cost(usd: float) -> str:
    """Format USD cost for display."""
    if usd >= 100:
        return f"${usd:.0f}"
    if usd >= 10:
        return f"${usd:.1f}"
    return f"${usd:.2f}"


def get_cost_color(usd: float) -> str:
    """Get color based on cost thresholds."""
    if usd >= 5.0:
        return "red"
    if usd >= 1.0:
        return "yellow"
    return "green"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def format_event_type(name: str) -> str:
    """Format event type with indicator."""
    indicators: dict[str, str] = {
        "tool_result": "T",
        "tool_use": "T",
        "api_request": "A",
        "api_response": "A",
        "user_prompt": "U",
        "session_start": "S",
        "session_end": "S",
    }
    indicator = indicators.get(name, "*")
    return f"[{indicator}]"


class OTelWidget(Widget):
    """Widget for displaying OpenTelemetry telemetry data.

    Supports 4 display modes: MICRO, MINIMIZED, MEDIUM, MAXIMIZED.
    Shows Claude Code metrics including tokens, cost, sessions, and events.
    """

    DEFAULT_CSS: ClassVar[str] = """
    OTelWidget {
        width: 100%;
        height: 100%;
        padding: 0;
    }

    OTelWidget .otel-content {
        width: 100%;
        height: 100%;
        padding: 0 1;
    }

    OTelWidget .micro-label {
        width: 100%;
        height: 100%;
        content-align: center middle;
    }

    OTelWidget .metric-line {
        width: 100%;
        height: 1;
    }

    OTelWidget .section-header {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $accent;
    }

    OTelWidget .event-line {
        width: 100%;
        height: 1;
        color: $text-muted;
    }

    OTelWidget .status-ok {
        color: $success;
    }

    OTelWidget .status-warn {
        color: $warning;
    }

    OTelWidget .status-error {
        color: $error;
    }

    OTelWidget .waiting {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    data: reactive[Any | None] = reactive(None)
    _display_mode: reactive[DisplayMode] = reactive(DisplayMode.MINIMIZED)

    def __init__(
        self,
        data: OTelData | None = None,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.data = data

    def compose(self) -> ComposeResult:
        """Compose the widget based on display mode."""
        if self.data is None:
            yield Label("Waiting for OTel data...", classes="waiting")
            return

        match self._display_mode:
            case DisplayMode.MICRO:
                yield Label(self._render_micro(), classes="micro-label")
            case DisplayMode.MINIMIZED:
                yield Static(self._render_minimized(), classes="otel-content")
            case DisplayMode.MEDIUM:
                yield Static(self._render_medium(), classes="otel-content")
            case DisplayMode.MAXIMIZED:
                yield Static(self._render_maximized(), classes="otel-content")

    def _render_micro(self) -> str:
        """Render ultra-compact single line."""
        if self.data is None:
            return "OTel: --"
        cost_color = get_cost_color(self.data.total_cost_usd)
        cost = format_cost(self.data.total_cost_usd)
        tokens = format_tokens(self.data.total_tokens)
        sessions = self.data.session_count
        return f"OTel: [{cost_color}]{cost}[/] | {tokens} tokens | {sessions} sessions"

    def _render_minimized(self) -> str:
        """Render compact 4-5 line view."""
        if self.data is None:
            return "Waiting for data..."
        d = self.data
        cost_color = get_cost_color(d.total_cost_usd)
        lines = [
            f"Cost:     [{cost_color}]{format_cost(d.total_cost_usd)}[/]",
            f"Tokens:   {format_tokens(d.total_tokens)} ({format_tokens(d.input_tokens)} in / {format_tokens(d.output_tokens)} out)",
            f"Sessions: {d.session_count}",
            f"Events:   {d.event_count}",
            f"Status:   {'[green]Receiving[/]' if d.receiver_running else '[dim]Waiting[/]'}",
        ]
        return "\n".join(lines)

    def _render_medium(self) -> str:
        """Render medium view with metrics + last 5 events."""
        if self.data is None:
            return "Waiting for data..."
        d = self.data
        cost_color = get_cost_color(d.total_cost_usd)
        lines = [
            "[bold]Metrics[/]",
            f"  Cost:       [{cost_color}]{format_cost(d.total_cost_usd)}[/]",
            f"  Tokens:     {format_tokens(d.total_tokens)} total",
            f"               {format_tokens(d.input_tokens)} in / {format_tokens(d.output_tokens)} out",
            f"  Cache:      {format_tokens(d.cache_read_tokens)} read / {format_tokens(d.cache_creation_tokens)} create",
            f"  Sessions:   {d.session_count}",
            f"  Duration:   {format_duration(d.active_duration_seconds)}",
            f"  Code:       {d.lines_of_code} lines | {d.num_commits} commits | {d.num_prs} PRs",
            "",
            f"[bold]Recent Events[/] ({d.event_count} total)",
        ]

        if d.recent_events:
            for event in d.recent_events[-5:]:
                ts = event.get("timestamp", "")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        ts = dt.strftime("%H:%M:%S")
                    except (ValueError, TypeError):
                        ts = ts[:8]
                name = event.get("name", "unknown")
                indicator = format_event_type(name)
                lines.append(f"  {ts} {indicator} {name}")
        else:
            lines.append("  No events yet")

        lines.append("")
        lines.append(f"Status: {'[green]Receiving[/]' if d.receiver_running else '[dim]Waiting for data...[/]'}")

        return "\n".join(lines)

    def _render_maximized(self) -> str:
        """Render full detail view with all metrics + event log."""
        if self.data is None:
            return "Waiting for data..."
        d = self.data
        cost_color = get_cost_color(d.total_cost_usd)
        lines = [
            "[bold]Token Usage[/]",
            f"  Total:            {format_tokens(d.total_tokens)} ({d.total_tokens:,})",
            f"  Input:            {format_tokens(d.input_tokens)} ({d.input_tokens:,})",
            f"  Output:           {format_tokens(d.output_tokens)} ({d.output_tokens:,})",
            f"  Cache Read:       {format_tokens(d.cache_read_tokens)} ({d.cache_read_tokens:,})",
            f"  Cache Creation:   {format_tokens(d.cache_creation_tokens)} ({d.cache_creation_tokens:,})",
            "",
            "[bold]Cost & Activity[/]",
            f"  Total Cost:       [{cost_color}]{format_cost(d.total_cost_usd)}[/]",
            f"  Sessions:         {d.session_count}",
            f"  Active Duration:  {format_duration(d.active_duration_seconds)}",
            f"  Lines of Code:    {d.lines_of_code:,}",
            f"  Commits:          {d.num_commits}",
            f"  Pull Requests:    {d.num_prs}",
            "",
            f"[bold]Event Log[/] ({d.event_count} total)",
        ]

        if d.recent_events:
            for event in d.recent_events[-20:]:
                ts = event.get("timestamp", "")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        ts = dt.strftime("%H:%M:%S")
                    except (ValueError, TypeError):
                        ts = ts[:8]
                name = event.get("name", "unknown")
                severity = event.get("severity", "INFO")
                indicator = format_event_type(name)
                attrs = event.get("attributes", {})
                attr_str = ""
                if attrs:
                    attr_parts = [f"{k}={v}" for k, v in list(attrs.items())[:3]]
                    attr_str = f" ({', '.join(attr_parts)})"
                sev_color = "red" if severity in ("ERROR", "FATAL") else "yellow" if severity == "WARN" else "dim"
                lines.append(f"  {ts} [{sev_color}]{severity:<5}[/] {indicator} {name}{attr_str}")
        else:
            lines.append("  No events yet")

        lines.append("")
        status = "[green]Receiving[/]" if d.receiver_running else "[dim]Waiting for data...[/]"
        last = ""
        if d.last_updated:
            last = f" (last: {d.last_updated.strftime('%H:%M:%S')})"
        lines.append(f"Status: {status}{last}")

        return "\n".join(lines)

    def watch_data(self, new_data: Any) -> None:
        """React to data changes by recomposing."""
        if self.is_mounted:
            self.recompose()

    def update_data(self, data: OTelData, mode: DisplayMode | None = None) -> None:
        """Update the widget with new data.

        Args:
            data: The new OTelData to display
            mode: Optional display mode to switch to
        """
        if mode is not None and mode != self._display_mode:
            self._display_mode = mode
        self.data = data
