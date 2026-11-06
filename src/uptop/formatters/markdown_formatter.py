"""Markdown formatter plugin for uptop CLI output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from uptop.models.base import MetricData, PluginType
from uptop.plugin_api.base import FormatterPlugin


class MarkdownFormatter(FormatterPlugin):
    """Format a system snapshot as readable Markdown."""

    name = "markdown"
    display_name = "Markdown Formatter"
    format_name = "markdown"
    cli_flag = "--markdown"
    file_extension = ".md"
    version = "0.1.0"
    description = "Format system metrics as Markdown"
    author = "uptop"

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return FORMATTER plugin type."""
        return PluginType.FORMATTER

    def format(self, data: dict[str, Any]) -> str:
        """Format a SystemSnapshot-like mapping as Markdown."""
        timestamp = data.get("timestamp")
        timestamp_text = (
            timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp or "")
        )
        lines = ["# uptop system snapshot", ""]
        if timestamp_text:
            lines.append(f"_Captured: {timestamp_text}_")
        if hostname := data.get("hostname"):
            lines.append(f"_Host: {hostname}_")

        for pane_name, pane_data in data.get("panes", {}).items():
            lines.extend(["", f"## {pane_name.replace('_', ' ').title()}", ""])
            if isinstance(pane_data, MetricData):
                values = pane_data.model_dump(mode="json")
            elif isinstance(pane_data, dict):
                values = pane_data
            else:
                lines.append(str(pane_data))
                continue

            for key, value in values.items():
                if key in {"timestamp", "source"}:
                    continue
                lines.append(f"- **{key.replace('_', ' ')}:** {value}")

        return "\n".join(lines) + "\n"
