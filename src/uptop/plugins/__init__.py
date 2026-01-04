"""Plugin management for uptop.

This module provides the plugin registry and discovery mechanisms:
- PluginRegistry: Central registry for all plugins
- Discovery via setuptools entry points
- Discovery via ~/.uptop/plugins/ directory
"""

from uptop.plugins.registry import PluginRegistry

__all__ = ["PluginRegistry"]
