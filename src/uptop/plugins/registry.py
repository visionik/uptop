"""Plugin registry and discovery for uptop.

This module provides the central plugin management system including:
- Discovery via setuptools entry points (installed packages)
- Discovery via directory scanning (~/.uptop/plugins/)
- Registration and lifecycle management
- Plugin lookup by name and type
- Dependency injection for plugin initialization
"""

from collections.abc import Iterator
import importlib
import importlib.metadata
import importlib.util
import logging
from pathlib import Path
import sys
import traceback
from typing import Any, TypeVar

from uptop.models.base import PluginMetadata, PluginType
from uptop.plugin_api.base import (
    API_VERSION,
    ActionPlugin,
    CollectorPlugin,
    FormatterPlugin,
    PanePlugin,
    PluginBase,
)

logger = logging.getLogger(__name__)

# Entry point group names for each plugin type
ENTRY_POINT_GROUPS = {
    PluginType.PANE: "uptop.panes",
    PluginType.COLLECTOR: "uptop.collectors",
    PluginType.FORMATTER: "uptop.formatters",
    PluginType.ACTION: "uptop.actions",
}

# Base class for each plugin type
# Using type instead of type[PluginBase] to allow abstract classes
PLUGIN_BASE_CLASSES: dict[PluginType, type] = {
    PluginType.PANE: PanePlugin,
    PluginType.COLLECTOR: CollectorPlugin,
    PluginType.FORMATTER: FormatterPlugin,
    PluginType.ACTION: ActionPlugin,
}

T = TypeVar("T", bound=PluginBase)


class PluginError(Exception):
    """Base exception for plugin-related errors.

    All plugin-related exceptions inherit from this class, allowing
    callers to catch all plugin errors with a single except clause.

    Attributes:
        plugin_name: Name of the plugin that caused the error (if known)
        cause: The underlying exception that caused this error (if any)
    """

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.plugin_name = plugin_name
        self.cause = cause

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.plugin_name:
            parts.insert(0, f"[{self.plugin_name}]")
        if self.cause:
            parts.append(f"(caused by: {self.cause})")
        return " ".join(parts)


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load.

    This can occur during:
    - Entry point resolution
    - Module import
    - Class instantiation
    """


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not registered."""


class PluginConflictError(PluginError):
    """Raised when multiple plugins have the same name."""


class PluginValidationError(PluginError):
    """Raised when a plugin fails validation.

    This can occur when:
    - Plugin class doesn't inherit from required base class
    - Plugin metadata is invalid
    - Plugin API version is incompatible
    - Required attributes are missing
    """


class PluginInitializationError(PluginError):
    """Raised when a plugin fails to initialize."""


class PluginLifecycleError(PluginError):
    """Raised when a plugin lifecycle operation fails (start/stop)."""


class PluginRegistry:
    """Central registry for all uptop plugins.

    Handles plugin discovery, registration, initialization, and lookup.
    Plugins can be loaded from:
    - setuptools entry points (pip-installed packages)
    - Local directory (~/.uptop/plugins/)

    Lifecycle:
        1. Create registry: registry = PluginRegistry()
        2. Discover plugins: registry.discover_all()
        3. Initialize: registry.initialize_all(config, dependencies)
        4. Start: registry.start_all()
        5. (use plugins...)
        6. Stop: registry.stop_all()
        7. Shutdown: registry.shutdown_all()

    Example:
        registry = PluginRegistry()
        registry.discover_all()
        registry.initialize_all(config, dependencies={"app": app})
        registry.start_all()

        cpu_pane = registry.get_pane("cpu")
        all_panes = registry.get_plugins_by_type(PluginType.PANE)

        registry.stop_all()
        registry.shutdown_all()
    """

    def __init__(self, plugin_dir: Path | None = None) -> None:
        """Initialize the plugin registry.

        Args:
            plugin_dir: Custom plugin directory. Defaults to ~/.uptop/plugins/
        """
        self._plugins: dict[str, PluginBase] = {}
        self._plugin_classes: dict[str, type[PluginBase]] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._plugin_dir = plugin_dir or Path.home() / ".uptop" / "plugins"
        self._initialized = False
        self._started = False
        self._dependencies: dict[str, Any] = {}
        self._failed_plugins: dict[str, str] = {}  # plugin_name -> error message

    @property
    def plugin_dir(self) -> Path:
        """Return the plugin directory path."""
        return self._plugin_dir

    @property
    def is_initialized(self) -> bool:
        """Return True if plugins have been initialized."""
        return self._initialized

    @property
    def is_started(self) -> bool:
        """Return True if plugins have been started."""
        return self._started

    @property
    def failed_plugins(self) -> dict[str, str]:
        """Return dict of failed plugin names to error messages."""
        return self._failed_plugins.copy()

    def discover_all(self, strict: bool = False) -> list[PluginMetadata]:
        """Discover plugins from all sources.

        Scans entry points and plugin directory for available plugins.

        Args:
            strict: If True, raise on first error. If False, log errors and continue.

        Returns:
            List of discovered plugin metadata

        Raises:
            PluginConflictError: If duplicate plugin names are found (only in strict mode)
            PluginLoadError: If plugin loading fails (only in strict mode)
        """
        discovered: list[PluginMetadata] = []
        self._failed_plugins.clear()

        logger.info("Starting plugin discovery...")

        # Discover from entry points first
        for plugin_type in PluginType:
            try:
                found = self._discover_entry_points(plugin_type, strict=strict)
                discovered.extend(found)
            except PluginError:
                if strict:
                    raise
                # Already logged in _discover_entry_points

        # Then discover from directory (can override entry points)
        try:
            found = self._discover_directory(strict=strict)
            discovered.extend(found)
        except PluginError:
            if strict:
                raise
            # Already logged in _discover_directory

        logger.info(
            f"Plugin discovery complete: {len(discovered)} plugins loaded, "
            f"{len(self._failed_plugins)} failed"
        )

        return discovered

    def _discover_entry_points(
        self, plugin_type: PluginType, strict: bool = False
    ) -> list[PluginMetadata]:
        """Discover plugins from setuptools entry points.

        Args:
            plugin_type: Type of plugins to discover
            strict: If True, raise on validation errors

        Returns:
            List of discovered plugin metadata

        Raises:
            PluginLoadError: If strict mode and loading fails
            PluginValidationError: If strict mode and validation fails
        """
        discovered: list[PluginMetadata] = []
        group = ENTRY_POINT_GROUPS[plugin_type]
        base_class = PLUGIN_BASE_CLASSES[plugin_type]

        logger.debug(f"Scanning entry point group: {group}")

        # Python 3.10+ API - entry_points() accepts group parameter
        try:
            entry_points = importlib.metadata.entry_points(group=group)
        except Exception as e:
            logger.error(f"Failed to get entry points for group {group}: {e}")
            if strict:
                raise PluginLoadError(
                    f"Failed to get entry points for {group}",
                    cause=e if isinstance(e, Exception) else None,
                ) from e
            return discovered

        for ep in entry_points:
            plugin_name = ep.name
            logger.debug(f"Loading entry point: {plugin_name} from {ep.value}")

            try:
                # Load the plugin class from the entry point
                plugin_class = ep.load()

                # Validate the plugin class
                self._validate_plugin_class_full(plugin_class, base_class, plugin_name, ep.value)

                # Get and validate metadata
                metadata = self._get_validated_metadata(plugin_class, plugin_name)

                # Register the plugin class (instantiation happens later)
                self._register_class(plugin_class, metadata)
                discovered.append(metadata)
                logger.info(f"Discovered entry point plugin: {metadata.name} v{metadata.version}")

            except PluginError as e:
                self._failed_plugins[plugin_name] = str(e)
                logger.error(f"Failed to load entry point plugin {plugin_name}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())
                if strict:
                    raise

            except Exception as e:
                error_msg = f"Unexpected error loading plugin: {e}"
                self._failed_plugins[plugin_name] = error_msg
                logger.error(f"Failed to load entry point plugin {plugin_name}: {error_msg}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())
                if strict:
                    raise PluginLoadError(
                        error_msg,
                        plugin_name=plugin_name,
                        cause=e,
                    ) from e

        return discovered

    def _discover_directory(self, strict: bool = False) -> list[PluginMetadata]:
        """Discover plugins from the plugin directory.

        Scans the plugin directory for .py files and loads plugin classes from them.
        Files starting with underscore are skipped. Subdirectories with __init__.py
        are treated as plugin packages.

        Args:
            strict: If True, raise on first error

        Returns:
            List of discovered plugin metadata

        Raises:
            PluginLoadError: If strict mode and loading fails
        """
        discovered: list[PluginMetadata] = []

        if not self._plugin_dir.exists():
            logger.debug(f"Plugin directory does not exist: {self._plugin_dir}")
            return discovered

        if not self._plugin_dir.is_dir():
            logger.warning(f"Plugin path is not a directory: {self._plugin_dir}")
            return discovered

        logger.debug(f"Scanning plugin directory: {self._plugin_dir}")

        # Scan .py files in the plugin directory
        for py_file in sorted(self._plugin_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                logger.debug(f"Skipping private file: {py_file.name}")
                continue

            found = self._load_plugins_from_file(py_file, strict=strict)
            discovered.extend(found)

        # Also scan subdirectories that are packages (have __init__.py)
        for subdir in sorted(self._plugin_dir.iterdir()):
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("_"):
                continue
            init_file = subdir / "__init__.py"
            if init_file.exists():
                found = self._load_plugins_from_file(init_file, strict=strict)
                discovered.extend(found)

        return discovered

    def _load_plugins_from_file(self, py_file: Path, strict: bool = False) -> list[PluginMetadata]:
        """Load plugins from a single Python file.

        Args:
            py_file: Path to the Python file
            strict: If True, raise on errors

        Returns:
            List of discovered plugin metadata
        """
        discovered: list[PluginMetadata] = []
        file_name = py_file.name

        logger.debug(f"Loading plugins from file: {py_file}")

        try:
            module = self._load_module_from_file(py_file)
            plugins_found = self._extract_plugins_from_module(module)

            if not plugins_found:
                logger.debug(f"No plugins found in {file_name}")
                return discovered

            for plugin_class in plugins_found:
                try:
                    plugin_name = getattr(plugin_class, "name", "unknown")
                    metadata = self._get_validated_metadata(plugin_class, plugin_name)

                    if metadata.name in self._plugins:
                        logger.warning(
                            f"Directory plugin {metadata.name} overrides "
                            f"existing plugin from {self._metadata[metadata.name].entry_point}"
                        )

                    self._register_class(plugin_class, metadata)
                    discovered.append(metadata)
                    logger.info(
                        f"Discovered directory plugin: {metadata.name} v{metadata.version} "
                        f"from {file_name}"
                    )

                except PluginError as e:
                    plugin_name = getattr(plugin_class, "name", file_name)
                    self._failed_plugins[plugin_name] = str(e)
                    logger.error(f"Failed to register plugin from {file_name}: {e}")
                    if strict:
                        raise

        except PluginLoadError as e:
            self._failed_plugins[file_name] = str(e)
            logger.error(f"Failed to load module from {file_name}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(traceback.format_exc())
            if strict:
                raise

        except Exception as e:
            error_msg = f"Unexpected error loading {file_name}: {e}"
            self._failed_plugins[file_name] = error_msg
            logger.error(error_msg)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(traceback.format_exc())
            if strict:
                raise PluginLoadError(
                    error_msg,
                    plugin_name=file_name,
                    cause=e,
                ) from e

        return discovered

    def _load_module_from_file(self, file_path: Path) -> object:
        """Dynamically load a Python module from a file path.

        Args:
            file_path: Path to the .py file

        Returns:
            The loaded module object

        Raises:
            PluginLoadError: If module cannot be loaded
        """
        module_name = f"uptop_plugin_{file_path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Cannot create module spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            del sys.modules[module_name]
            raise PluginLoadError(f"Failed to execute module {file_path}: {e}") from e

        return module

    def _extract_plugins_from_module(self, module: object) -> list[type[PluginBase]]:
        """Extract all plugin classes from a module.

        Args:
            module: The loaded module to inspect

        Returns:
            List of plugin class types found in the module
        """
        plugins: list[type[PluginBase]] = []

        for name in dir(module):
            if name.startswith("_"):
                continue

            obj = getattr(module, name)

            if not isinstance(obj, type):
                continue

            if obj in (PanePlugin, CollectorPlugin, FormatterPlugin, ActionPlugin, PluginBase):
                continue

            if issubclass(obj, PluginBase):
                plugins.append(obj)

        return plugins

    def _validate_plugin_class(self, plugin_class: type, expected_base: type) -> bool:
        """Validate that a plugin class inherits from the expected base.

        Args:
            plugin_class: The class to validate
            expected_base: The expected base class

        Returns:
            True if valid, False otherwise
        """
        return isinstance(plugin_class, type) and issubclass(plugin_class, expected_base)

    def _validate_plugin_class_full(
        self,
        plugin_class: type,
        expected_base: type,
        plugin_name: str,
        entry_point: str,
    ) -> None:
        """Perform full validation of a plugin class.

        Args:
            plugin_class: The class to validate
            expected_base: The expected base class
            plugin_name: Name for error messages
            entry_point: Entry point string for error messages

        Raises:
            PluginValidationError: If validation fails
        """
        # Check it's a class
        if not isinstance(plugin_class, type):
            raise PluginValidationError(
                f"Entry point '{entry_point}' does not resolve to a class",
                plugin_name=plugin_name,
            )

        # Check inheritance
        if not issubclass(plugin_class, expected_base):
            raise PluginValidationError(
                f"Plugin class does not inherit from {expected_base.__name__}",
                plugin_name=plugin_name,
            )

        # Check required attributes
        if not hasattr(plugin_class, "name") or not plugin_class.name:
            raise PluginValidationError(
                "Plugin class is missing 'name' attribute",
                plugin_name=plugin_name,
            )

        if not hasattr(plugin_class, "display_name") or not plugin_class.display_name:
            raise PluginValidationError(
                "Plugin class is missing 'display_name' attribute",
                plugin_name=plugin_name,
            )

        # Check API version compatibility
        plugin_api_version = getattr(plugin_class, "api_version", None)
        if plugin_api_version and not self._is_api_compatible(plugin_api_version):
            raise PluginValidationError(
                f"Plugin API version {plugin_api_version} is incompatible "
                f"with current API version {API_VERSION}",
                plugin_name=plugin_name,
            )

    def _is_api_compatible(self, plugin_api_version: str) -> bool:
        """Check if a plugin's API version is compatible with the current version.

        Currently uses major version matching - plugins with the same major
        version as the API are considered compatible.

        Args:
            plugin_api_version: The plugin's declared API version (e.g., "1.0")

        Returns:
            True if compatible, False otherwise
        """
        try:
            plugin_major = int(plugin_api_version.split(".")[0])
            current_major = int(API_VERSION.split(".")[0])
            return plugin_major == current_major
        except (ValueError, IndexError):
            # If version parsing fails, consider it incompatible
            return False

    def _get_validated_metadata(
        self, plugin_class: type[PluginBase], plugin_name: str
    ) -> PluginMetadata:
        """Get and validate metadata from a plugin class.

        Args:
            plugin_class: The plugin class
            plugin_name: Name for error messages

        Returns:
            Validated PluginMetadata

        Raises:
            PluginValidationError: If metadata is invalid
        """
        try:
            metadata = plugin_class.get_metadata()
        except Exception as e:
            raise PluginValidationError(
                f"Failed to get metadata: {e}",
                plugin_name=plugin_name,
                cause=e,
            ) from e

        # Validate the metadata
        if not metadata.name:
            raise PluginValidationError(
                "Plugin metadata has empty name",
                plugin_name=plugin_name,
            )

        # Name must match the class attribute
        if metadata.name != plugin_class.name:
            raise PluginValidationError(
                f"Metadata name '{metadata.name}' does not match "
                f"class attribute '{plugin_class.name}'",
                plugin_name=plugin_name,
            )

        return metadata

    def _register_class(self, plugin_class: type[PluginBase], metadata: PluginMetadata) -> None:
        """Register a plugin class in the registry.

        The plugin is instantiated immediately but not initialized until
        initialize_all() is called.

        Args:
            plugin_class: The plugin class to register
            metadata: The plugin's metadata

        Raises:
            PluginConflictError: If a plugin with this name already exists
            PluginLoadError: If plugin instantiation fails
        """
        name = metadata.name

        # Check for conflicts (but allow same entry_point to override)
        if name in self._plugins and name in self._metadata:
            existing = self._metadata[name]
            if existing.entry_point != metadata.entry_point:
                raise PluginConflictError(
                    f"Plugin name conflict: '{name}' registered by both "
                    f"'{existing.entry_point}' and '{metadata.entry_point}'",
                    plugin_name=name,
                )

        # Instantiate the plugin
        try:
            plugin_instance = plugin_class()
        except Exception as e:
            raise PluginLoadError(
                f"Failed to instantiate plugin class: {e}",
                plugin_name=name,
                cause=e,
            ) from e

        # Store in registry
        self._plugins[name] = plugin_instance
        self._plugin_classes[name] = plugin_class
        self._metadata[name] = metadata

    def register(self, plugin: PluginBase) -> None:
        """Manually register a plugin instance.

        Args:
            plugin: The plugin instance to register

        Raises:
            PluginConflictError: If a plugin with this name already exists
        """
        metadata = plugin.get_metadata()
        name = metadata.name

        if name in self._plugins:
            raise PluginConflictError(f"Plugin '{name}' is already registered")

        self._plugins[name] = plugin
        self._metadata[name] = metadata

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry.

        The plugin is stopped and shutdown before removal.

        Args:
            name: The plugin name to unregister

        Raises:
            PluginNotFoundError: If no plugin with this name exists
        """
        if name not in self._plugins:
            raise PluginNotFoundError(
                f"Plugin '{name}' is not registered",
                plugin_name=name,
            )

        plugin = self._plugins[name]

        # Stop the plugin if running
        if hasattr(plugin, "stop") and callable(plugin.stop):
            try:
                plugin.stop()
            except Exception as e:
                logger.warning(f"Error stopping plugin {name} during unregister: {e}")

        # Shutdown the plugin if initialized
        if plugin._initialized:
            try:
                plugin.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down plugin {name} during unregister: {e}")

        # Remove from all registries
        del self._plugins[name]
        del self._metadata[name]
        if name in self._plugin_classes:
            del self._plugin_classes[name]
        if name in self._failed_plugins:
            del self._failed_plugins[name]

        logger.debug(f"Unregistered plugin: {name}")

    def initialize_all(
        self,
        config: dict[str, dict[str, Any]] | None = None,
        dependencies: dict[str, Any] | None = None,
    ) -> list[str]:
        """Initialize all registered plugins with configuration and dependencies.

        This method injects dependencies and configuration into each plugin.
        Plugins that fail to initialize are disabled but not removed.

        Args:
            config: Dict mapping plugin names to their config dicts
            dependencies: Dict of dependencies to inject into plugins
                         (e.g., {"app": app, "scheduler": scheduler})

        Returns:
            List of plugin names that failed to initialize
        """
        config = config or {}
        self._dependencies = dependencies or {}
        failed: list[str] = []

        logger.info(f"Initializing {len(self._plugins)} plugins...")

        for name, plugin in self._plugins.items():
            try:
                plugin_config = config.get(name, {})

                # Inject dependencies if the plugin has an inject method
                if hasattr(plugin, "inject") and callable(plugin.inject):
                    plugin.inject(**self._dependencies)

                plugin.initialize(plugin_config)
                logger.debug(f"Initialized plugin: {name}")

            except Exception as e:
                error_msg = f"Failed to initialize: {e}"
                self._failed_plugins[name] = error_msg
                logger.error(f"Failed to initialize plugin {name}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())
                plugin.enabled = False
                failed.append(name)

        self._initialized = True
        logger.info(
            f"Plugin initialization complete: "
            f"{len(self._plugins) - len(failed)} succeeded, {len(failed)} failed"
        )
        return failed

    def start_all(self) -> list[str]:
        """Start all enabled plugins.

        This is called after initialization to begin plugin operations.
        Plugins can override the start() method for custom startup logic.

        Returns:
            List of plugin names that failed to start
        """
        if not self._initialized:
            logger.warning("start_all() called before initialize_all()")

        failed: list[str] = []
        started_count = 0

        logger.info("Starting plugins...")

        for name, plugin in self._plugins.items():
            if not plugin.enabled:
                logger.debug(f"Skipping disabled plugin: {name}")
                continue

            try:
                if hasattr(plugin, "start") and callable(plugin.start):
                    plugin.start()
                started_count += 1
                logger.debug(f"Started plugin: {name}")

            except Exception as e:
                error_msg = f"Failed to start: {e}"
                self._failed_plugins[name] = error_msg
                logger.error(f"Failed to start plugin {name}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())
                plugin.enabled = False
                failed.append(name)

        self._started = True
        logger.info(f"Plugin startup complete: {started_count} started, {len(failed)} failed")
        return failed

    def stop_all(self) -> list[str]:
        """Stop all running plugins.

        This is called before shutdown to gracefully stop plugin operations.
        Plugins can override the stop() method for custom stop logic.

        Returns:
            List of plugin names that failed to stop
        """
        failed: list[str] = []
        stopped_count = 0

        logger.info("Stopping plugins...")

        # Stop in reverse order of registration
        for name in reversed(list(self._plugins.keys())):
            plugin = self._plugins[name]

            if not plugin.enabled:
                continue

            try:
                if hasattr(plugin, "stop") and callable(plugin.stop):
                    plugin.stop()
                stopped_count += 1
                logger.debug(f"Stopped plugin: {name}")

            except Exception as e:
                logger.error(f"Error stopping plugin {name}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())
                failed.append(name)

        self._started = False
        logger.info(f"Plugin stop complete: {stopped_count} stopped, {len(failed)} failed")
        return failed

    def shutdown_all(self) -> list[str]:
        """Shutdown all registered plugins.

        This performs cleanup after plugins are stopped. It calls shutdown()
        on each plugin and clears the initialized state.

        Returns:
            List of plugin names that failed to shutdown
        """
        # Stop first if still running
        if self._started:
            self.stop_all()

        failed: list[str] = []

        logger.info("Shutting down plugins...")

        # Shutdown in reverse order
        for name in reversed(list(self._plugins.keys())):
            plugin = self._plugins[name]

            try:
                plugin.shutdown()
                logger.debug(f"Shutdown plugin: {name}")

            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())
                failed.append(name)

        self._initialized = False
        self._dependencies.clear()
        logger.info("Plugin shutdown complete")
        return failed

    def get(self, name: str) -> PluginBase:
        """Get a plugin by name.

        Args:
            name: The plugin name

        Returns:
            The plugin instance

        Raises:
            PluginNotFoundError: If no plugin with this name exists
        """
        if name not in self._plugins:
            raise PluginNotFoundError(f"Plugin '{name}' is not registered")
        return self._plugins[name]

    def get_pane(self, name: str) -> PanePlugin:
        """Get a pane plugin by name.

        Args:
            name: The pane plugin name

        Returns:
            The PanePlugin instance

        Raises:
            PluginNotFoundError: If not found or wrong type
        """
        plugin = self.get(name)
        if not isinstance(plugin, PanePlugin):
            raise PluginNotFoundError(f"Plugin '{name}' is not a PanePlugin")
        return plugin

    def get_plugins_by_type(self, plugin_type: PluginType) -> list[PluginBase]:
        """Get all plugins of a specific type.

        Args:
            plugin_type: The type of plugins to retrieve

        Returns:
            List of plugin instances matching the type
        """
        base_class = PLUGIN_BASE_CLASSES[plugin_type]
        return [p for p in self._plugins.values() if isinstance(p, base_class)]

    def get_all_metadata(self) -> list[PluginMetadata]:
        """Get metadata for all registered plugins.

        Returns:
            List of all plugin metadata
        """
        return list(self._metadata.values())

    def get_enabled_plugins(self) -> list[PluginBase]:
        """Get all enabled plugins.

        Returns:
            List of enabled plugin instances
        """
        return [p for p in self._plugins.values() if p.enabled]

    def get_collector(self, name: str) -> CollectorPlugin:
        """Get a collector plugin by name.

        Args:
            name: The collector plugin name

        Returns:
            The CollectorPlugin instance

        Raises:
            PluginNotFoundError: If not found or wrong type
        """
        plugin = self.get(name)
        if not isinstance(plugin, CollectorPlugin):
            raise PluginNotFoundError(
                f"Plugin '{name}' is not a CollectorPlugin",
                plugin_name=name,
            )
        return plugin

    def get_formatter(self, name: str) -> FormatterPlugin:
        """Get a formatter plugin by name.

        Args:
            name: The formatter plugin name

        Returns:
            The FormatterPlugin instance

        Raises:
            PluginNotFoundError: If not found or wrong type
        """
        plugin = self.get(name)
        if not isinstance(plugin, FormatterPlugin):
            raise PluginNotFoundError(
                f"Plugin '{name}' is not a FormatterPlugin",
                plugin_name=name,
            )
        return plugin

    def get_action(self, name: str) -> ActionPlugin:
        """Get an action plugin by name.

        Args:
            name: The action plugin name

        Returns:
            The ActionPlugin instance

        Raises:
            PluginNotFoundError: If not found or wrong type
        """
        plugin = self.get(name)
        if not isinstance(plugin, ActionPlugin):
            raise PluginNotFoundError(
                f"Plugin '{name}' is not an ActionPlugin",
                plugin_name=name,
            )
        return plugin

    def clear(self) -> None:
        """Clear all registered plugins.

        This shuts down all plugins and removes them from the registry.
        """
        if self._initialized:
            self.shutdown_all()

        self._plugins.clear()
        self._plugin_classes.clear()
        self._metadata.clear()
        self._failed_plugins.clear()
        logger.debug("Registry cleared")

    def __len__(self) -> int:
        """Return the number of registered plugins."""
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        """Check if a plugin is registered by name."""
        return name in self._plugins

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered plugin names."""
        return iter(self._plugins)

    def __repr__(self) -> str:
        """Return a string representation of the registry."""
        return (
            f"PluginRegistry("
            f"plugins={len(self._plugins)}, "
            f"initialized={self._initialized}, "
            f"started={self._started})"
        )
