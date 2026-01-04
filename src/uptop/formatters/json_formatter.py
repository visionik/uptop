"""JSON Formatter Plugin for uptop.

This module provides a JSON output formatter for collected pane data.
It implements the FormatterPlugin interface and uses Pydantic's
model_dump() for serialization with proper datetime handling.

Features:
- Serializes MetricData to valid JSON
- Supports pretty-printing (indented) or compact output
- Handles datetime serialization in ISO format
- Includes timestamp in output
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from uptop.models.base import MetricData, PluginType
from uptop.plugin_api.base import FormatterPlugin


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class JsonFormatter(FormatterPlugin):
    """JSON formatter plugin for uptop CLI output.

    Converts collected pane data to JSON format for machine-readable
    output. Supports both pretty-printed and compact JSON output.

    Class Attributes:
        name: Plugin identifier ("json")
        display_name: Human-readable name for UI
        format_name: Format identifier for CLI selection
        cli_flag: CLI flag to select this format
        file_extension: Default file extension for output files

    Instance Attributes:
        pretty_print: Whether to format with indentation (default: True)
    """

    name: str = "json"
    display_name: str = "JSON Formatter"
    format_name: str = "JSON"
    cli_flag: str = "--json"
    file_extension: str = ".json"
    version: str = "0.1.0"
    description: str = "Format system metrics as JSON output"
    author: str = "uptop"

    def __init__(self, pretty_print: bool = True) -> None:
        """Initialize the JSON formatter.

        Args:
            pretty_print: If True, output indented JSON (default: True).
                         If False, output compact single-line JSON.
        """
        super().__init__()
        self.pretty_print = pretty_print

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the formatter with configuration.

        Args:
            config: Plugin-specific configuration. Supports:
                - pretty_print (bool): Whether to indent output
        """
        super().initialize(config)
        if config:
            self.pretty_print = config.get("pretty_print", self.pretty_print)

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return FORMATTER plugin type."""
        return PluginType.FORMATTER

    def format(self, data: dict[str, Any]) -> str:
        """Format system data as a JSON string.

        Accepts a dictionary containing pane data (MetricData instances
        or already-serialized dicts) and returns a valid JSON string.

        The output includes:
        - timestamp: When the snapshot was taken (ISO format)
        - panes: Dictionary of pane name -> serialized pane data

        Args:
            data: Dictionary containing SystemSnapshot-like data.
                  Expected keys:
                  - "panes": dict[str, MetricData] or dict[str, dict]
                  - "timestamp": datetime (optional, defaults to now)
                  - "hostname": str (optional)
                  Any extra keys are preserved.

        Returns:
            JSON string representation of the data.

        Example:
            >>> formatter = JsonFormatter(pretty_print=True)
            >>> data = {"panes": {"cpu": cpu_data}, "hostname": "myhost"}
            >>> json_str = formatter.format(data)
            >>> print(json_str)
            {
              "timestamp": "2024-01-15T10:30:00.000000Z",
              "hostname": "myhost",
              "panes": {
                "cpu": { ... }
              }
            }
        """
        output: dict[str, Any] = {}

        # Get or create timestamp
        timestamp = data.get("timestamp")
        if timestamp is None:
            timestamp = _utcnow()
        if isinstance(timestamp, datetime):
            output["timestamp"] = timestamp.isoformat()
        else:
            output["timestamp"] = str(timestamp)

        # Copy hostname if present
        if "hostname" in data:
            output["hostname"] = data["hostname"]

        # Serialize panes data
        panes = data.get("panes", {})
        serialized_panes: dict[str, Any] = {}

        for pane_name, pane_data in panes.items():
            if isinstance(pane_data, MetricData):
                # Use Pydantic's model_dump with mode="json" for proper serialization
                serialized_panes[pane_name] = pane_data.model_dump(mode="json")
            elif isinstance(pane_data, dict):
                # Already a dict, just use it
                serialized_panes[pane_name] = pane_data
            else:
                # Try to serialize as-is
                serialized_panes[pane_name] = pane_data

        output["panes"] = serialized_panes

        # Copy any additional top-level keys
        for key, value in data.items():
            if key not in ("timestamp", "hostname", "panes"):
                if isinstance(value, datetime):
                    output[key] = value.isoformat()
                elif isinstance(value, MetricData):
                    output[key] = value.model_dump(mode="json")
                else:
                    output[key] = value

        # Serialize to JSON
        if self.pretty_print:
            return json.dumps(output, indent=2, ensure_ascii=False)
        else:
            return json.dumps(output, ensure_ascii=False, separators=(",", ":"))

    def format_panes(self, panes: dict[str, MetricData]) -> str:
        """Format a dictionary of pane data as JSON.

        Convenience method that wraps pane data in the expected format.

        Args:
            panes: Dictionary mapping pane names to MetricData instances.

        Returns:
            JSON string representation.
        """
        return self.format({"panes": panes})

    def get_ai_help_docs(self) -> str:
        """Return markdown documentation for --ai-help output.

        Returns:
            Markdown-formatted string describing the plugin.
        """
        return """## JSON Formatter

The JSON Formatter outputs collected metrics as valid JSON.

### Usage
```bash
uptop --json           # Output metrics as JSON
uptop --json --once    # Single snapshot, exit immediately
```

### Configuration Options
- `pretty_print`: Whether to indent output (default: true)

### Output Format
```json
{
  "timestamp": "2024-01-15T10:30:00.000000Z",
  "hostname": "myhost",
  "panes": {
    "cpu": { ... },
    "memory": { ... },
    "disk": { ... },
    "network": { ... }
  }
}
```

### Notes
- All timestamps are in ISO 8601 format with UTC timezone
- Datetime fields use Pydantic's model_dump(mode="json") for serialization
- Nested MetricData objects are fully serialized
- Use compact mode (pretty_print=false) for streaming/logging
"""
