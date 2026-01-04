"""Lazy loading utilities for uptop plugins.

This module provides utilities for deferring heavy imports and plugin
initialization until they are actually needed, improving startup time.

The LazyPluginLoader defers plugin discovery and initialization until
the plugins are actually accessed, while providing immediate access to
essential plugins.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from uptop.plugin_api.base import BasePlugin
    from uptop.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


class LazyModuleLoader:
    """Lazy loader for Python modules.

    Defers the actual import of a module until it's accessed,
    reducing startup time for modules that may not be immediately needed.
    """

    def __init__(self, module_path: str) -> None:
        """Initialize the lazy loader.

        Args:
            module_path: Full dotted path to the module (e.g., 'uptop.plugins.cpu')
        """
        self._module_path = module_path
        self._module: Any = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if the module has been loaded."""
        return self._loaded

    def load(self) -> Any:
        """Load the module if not already loaded.

        Returns:
            The loaded module
        """
        if not self._loaded:
            import importlib

            logger.debug(f"Lazy loading module: {self._module_path}")
            self._module = importlib.import_module(self._module_path)
            self._loaded = True
        return self._module

    def __getattr__(self, name: str) -> Any:
        """Get attribute from the module, loading it first if necessary.

        Args:
            name: Attribute name to get

        Returns:
            The attribute value from the loaded module
        """
        return getattr(self.load(), name)


class LazyPluginFactory:
    """Factory that creates plugins lazily.

    Defers actual plugin instantiation until the plugin is first accessed,
    reducing memory usage and startup time.
    """

    def __init__(
        self,
        module_path: str,
        class_name: str,
        *,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the lazy plugin factory.

        Args:
            module_path: Full dotted path to the module containing the plugin
            class_name: Name of the plugin class to instantiate
            args: Positional arguments for plugin constructor
            kwargs: Keyword arguments for plugin constructor
        """
        self._module_path = module_path
        self._class_name = class_name
        self._args = args
        self._kwargs = kwargs or {}
        self._instance: BasePlugin | None = None

    @property
    def is_instantiated(self) -> bool:
        """Check if the plugin has been instantiated."""
        return self._instance is not None

    def get_instance(self) -> BasePlugin:
        """Get the plugin instance, creating it if necessary.

        Returns:
            The plugin instance
        """
        if self._instance is None:
            import importlib

            logger.debug(f"Lazy instantiating plugin: {self._class_name}")
            module = importlib.import_module(self._module_path)
            plugin_class = getattr(module, self._class_name)
            self._instance = plugin_class(*self._args, **self._kwargs)
        return self._instance


# Define essential plugins that should be loaded immediately
ESSENTIAL_PLUGINS = frozenset({"cpu", "memory", "processes"})

# Define plugins that can be deferred
DEFERRABLE_PLUGINS = frozenset({"network", "disk"})


def create_essential_plugin_factories() -> dict[str, LazyPluginFactory]:
    """Create factories for essential plugins.

    Essential plugins are loaded immediately as they're typically
    visible in the default layout.

    Returns:
        Dictionary mapping plugin names to their factories
    """
    return {
        "cpu": LazyPluginFactory("uptop.plugins.cpu", "CPUPane"),
        "memory": LazyPluginFactory("uptop.plugins.memory", "MemoryPane"),
        "processes": LazyPluginFactory("uptop.plugins.processes", "ProcessPane"),
    }


def create_deferred_plugin_factories() -> dict[str, LazyPluginFactory]:
    """Create factories for deferrable plugins.

    Deferred plugins are only instantiated when first accessed,
    improving initial startup time.

    Returns:
        Dictionary mapping plugin names to their factories
    """
    return {
        "network": LazyPluginFactory("uptop.plugins.network", "NetworkPane"),
        "disk": LazyPluginFactory("uptop.plugins.disk", "DiskPane"),
    }


class LazyPluginRegistry:
    """A plugin registry that supports lazy loading.

    Wraps the standard PluginRegistry but defers plugin instantiation
    for non-essential plugins until they're first accessed.
    """

    def __init__(self, registry: PluginRegistry) -> None:
        """Initialize the lazy registry.

        Args:
            registry: The underlying plugin registry to wrap
        """
        self._registry = registry
        self._deferred_factories: dict[str, LazyPluginFactory] = {}
        self._initialized_plugins: set[str] = set()

    def register_deferred(
        self,
        name: str,
        module_path: str,
        class_name: str,
    ) -> None:
        """Register a plugin for deferred loading.

        Args:
            name: Plugin name
            module_path: Module path containing the plugin
            class_name: Class name of the plugin
        """
        self._deferred_factories[name] = LazyPluginFactory(module_path, class_name)
        logger.debug(f"Registered deferred plugin: {name}")

    def ensure_loaded(self, name: str) -> None:
        """Ensure a specific plugin is loaded and registered.

        Args:
            name: Name of the plugin to ensure is loaded
        """
        if name in self._initialized_plugins:
            return

        if name in self._deferred_factories:
            factory = self._deferred_factories[name]
            plugin = factory.get_instance()
            self._registry.register(plugin)
            plugin.initialize()
            self._initialized_plugins.add(name)
            logger.info(f"Lazily loaded plugin: {name}")

    def get(self, name: str) -> BasePlugin:
        """Get a plugin, loading it first if necessary.

        Args:
            name: Plugin name

        Returns:
            The plugin instance
        """
        self.ensure_loaded(name)
        return self._registry.get(name)

    @property
    def registry(self) -> PluginRegistry:
        """Get the underlying registry."""
        return self._registry

    def load_all_deferred(self) -> None:
        """Load all deferred plugins.

        Useful when all plugins need to be available, such as
        before running a full refresh.
        """
        for name in list(self._deferred_factories.keys()):
            self.ensure_loaded(name)


def setup_plugins_with_lazy_loading(
    registry: PluginRegistry,
    *,
    defer_non_essential: bool = True,
) -> LazyPluginRegistry:
    """Set up plugins with optional lazy loading for non-essential ones.

    Args:
        registry: The plugin registry to use
        defer_non_essential: Whether to defer loading of non-essential plugins

    Returns:
        LazyPluginRegistry wrapper with lazy loading support
    """
    lazy_registry = LazyPluginRegistry(registry)

    # Always load essential plugins immediately
    essential_factories = create_essential_plugin_factories()
    for name, factory in essential_factories.items():
        plugin = factory.get_instance()
        registry.register(plugin)
        plugin.initialize()
        lazy_registry._initialized_plugins.add(name)
        logger.info(f"Loaded essential plugin: {name}")

    # Either defer or immediately load non-essential plugins
    deferred_factories = create_deferred_plugin_factories()
    if defer_non_essential:
        for name, factory in deferred_factories.items():
            lazy_registry.register_deferred(
                name,
                factory._module_path,
                factory._class_name,
            )
    else:
        for name, factory in deferred_factories.items():
            plugin = factory.get_instance()
            registry.register(plugin)
            plugin.initialize()
            lazy_registry._initialized_plugins.add(name)
            logger.info(f"Loaded plugin: {name}")

    return lazy_registry
