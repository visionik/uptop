"""Formatters package for uptop.

This package contains formatter plugins that convert system data to various output formats:

- JsonFormatter: JSON output for machine-readable data
- PrometheusFormatter: Prometheus metrics format for monitoring integration

Additional formatters (Markdown, etc.) will be added in future phases.
"""

from uptop.formatters.json_formatter import JsonFormatter
from uptop.formatters.prometheus import PrometheusFormatter

__all__ = [
    "JsonFormatter",
    "PrometheusFormatter",
]
