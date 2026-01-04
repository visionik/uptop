"""Plugin API for uptop extensions.

This module provides the abstract base classes that all uptop plugins must implement:
- PanePlugin: For creating new monitoring panes
- CollectorPlugin: For contributing data to existing panes
- FormatterPlugin: For custom output formats
- ActionPlugin: For keyboard-triggered actions

Plugin API Version: 1.0
"""

from uptop.plugin_api.base import (
    API_VERSION,
    ActionPlugin,
    CollectorPlugin,
    FormatterPlugin,
    PanePlugin,
    PluginBase,
)

__all__ = [
    "API_VERSION",
    "PluginBase",
    "PanePlugin",
    "CollectorPlugin",
    "FormatterPlugin",
    "ActionPlugin",
]
