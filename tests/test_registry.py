"""Tests for uptop plugin registry."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pydantic import BaseModel
import pytest

from uptop.models import MetricData, PluginType
from uptop.plugin_api import ActionPlugin, CollectorPlugin, FormatterPlugin, PanePlugin
from uptop.plugins.registry import (
    PluginConflictError,
    PluginError,
    PluginInitializationError,
    PluginLifecycleError,
    PluginLoadError,
    PluginNotFoundError,
    PluginRegistry,
    PluginValidationError,
)


class SampleData(MetricData):
    """Sample data model for testing."""

    value: int = 0


class SamplePanePlugin(PanePlugin):
    """Sample pane plugin for testing."""

    name = "sample_pane"
    display_name = "Sample Pane"
    description = "A sample pane for testing"

    async def collect_data(self) -> SampleData:
        return SampleData(value=42, source="sample")

    def render_tui(self, data: MetricData) -> Any:
        return MagicMock()

    def get_schema(self) -> type[BaseModel]:
        return SampleData


class AnotherPanePlugin(PanePlugin):
    """Another sample pane plugin for testing."""

    name = "another_pane"
    display_name = "Another Pane"

    async def collect_data(self) -> SampleData:
        return SampleData(value=100, source="another")

    def render_tui(self, data: MetricData) -> Any:
        return MagicMock()

    def get_schema(self) -> type[BaseModel]:
        return SampleData


class PluginWithLifecycle(PanePlugin):
    """Plugin that tracks lifecycle method calls."""

    name = "lifecycle_test"
    display_name = "Lifecycle Test Plugin"

    def __init__(self) -> None:
        super().__init__()
        self.started = False
        self.stopped = False
        self.inject_calls: list[dict] = []

    async def collect_data(self) -> SampleData:
        return SampleData(value=1, source="lifecycle")

    def render_tui(self, data: MetricData) -> Any:
        return MagicMock()

    def get_schema(self) -> type[BaseModel]:
        return SampleData

    def inject(self, **kwargs: Any) -> None:
        """Track dependency injection calls."""
        self.inject_calls.append(kwargs)

    def start(self) -> None:
        """Track start calls."""
        self.started = True

    def stop(self) -> None:
        """Track stop calls."""
        self.stopped = True


class FailingPlugin(PanePlugin):
    """Plugin that fails during initialization."""

    name = "failing_plugin"
    display_name = "Failing Plugin"

    def initialize(self, config: dict | None = None) -> None:
        raise RuntimeError("Intentional init failure")

    async def collect_data(self) -> SampleData:
        return SampleData(value=0, source="failing")

    def render_tui(self, data: MetricData) -> Any:
        return MagicMock()

    def get_schema(self) -> type[BaseModel]:
        return SampleData


class SampleCollectorPlugin(CollectorPlugin):
    """Sample collector plugin for testing."""

    name = "sample_collector"
    display_name = "Sample Collector"
    target_pane = "sample_pane"

    def collect(self, context: Any) -> dict[str, Any]:
        return {"extra_field": "value"}


class SampleFormatterPlugin(FormatterPlugin):
    """Sample formatter plugin for testing."""

    name = "sample_formatter"
    display_name = "Sample Formatter"
    format_name = "sample"
    cli_flag = "--sample"

    def format(self, data: dict[str, Any]) -> str:
        return str(data)


class SampleActionPlugin(ActionPlugin):
    """Sample action plugin for testing."""

    name = "sample_action"
    display_name = "Sample Action"
    keyboard_shortcut = "x"

    def can_execute(self, context: Any) -> bool:
        return True

    async def execute(self, context: Any) -> Any:
        return {"success": True}


class TestPluginExceptions:
    """Tests for plugin exception hierarchy."""

    def test_plugin_error_is_base(self) -> None:
        """Test PluginError is the base exception."""
        assert issubclass(PluginLoadError, PluginError)
        assert issubclass(PluginNotFoundError, PluginError)
        assert issubclass(PluginConflictError, PluginError)
        assert issubclass(PluginValidationError, PluginError)
        assert issubclass(PluginInitializationError, PluginError)
        assert issubclass(PluginLifecycleError, PluginError)

    def test_exceptions_can_be_raised(self) -> None:
        """Test exceptions can be raised with messages."""
        with pytest.raises(PluginLoadError, match="load failed"):
            raise PluginLoadError("load failed")

        with pytest.raises(PluginNotFoundError, match="not found"):
            raise PluginNotFoundError("not found")

        with pytest.raises(PluginConflictError, match="conflict"):
            raise PluginConflictError("conflict")

        with pytest.raises(PluginValidationError, match="validation"):
            raise PluginValidationError("validation failed")

        with pytest.raises(PluginInitializationError, match="init"):
            raise PluginInitializationError("init failed")

        with pytest.raises(PluginLifecycleError, match="lifecycle"):
            raise PluginLifecycleError("lifecycle error")

    def test_exception_with_plugin_name(self) -> None:
        """Test exceptions include plugin name in string representation."""
        error = PluginLoadError("load failed", plugin_name="test_plugin")
        assert "test_plugin" in str(error)
        assert "load failed" in str(error)
        assert error.plugin_name == "test_plugin"

    def test_exception_with_cause(self) -> None:
        """Test exceptions include cause information."""
        cause = ValueError("underlying error")
        error = PluginLoadError("load failed", cause=cause)
        assert "caused by" in str(error)
        assert "underlying error" in str(error)
        assert error.cause is cause

    def test_exception_full_context(self) -> None:
        """Test exceptions with both plugin name and cause."""
        cause = RuntimeError("root cause")
        error = PluginValidationError(
            "validation failed",
            plugin_name="my_plugin",
            cause=cause,
        )
        error_str = str(error)
        assert "[my_plugin]" in error_str
        assert "validation failed" in error_str
        assert "root cause" in error_str


class TestPluginRegistry:
    """Tests for PluginRegistry class."""

    def test_init_default_plugin_dir(self) -> None:
        """Test default plugin directory."""
        registry = PluginRegistry()
        expected = Path.home() / ".uptop" / "plugins"
        assert registry.plugin_dir == expected

    def test_init_custom_plugin_dir(self) -> None:
        """Test custom plugin directory."""
        custom_dir = Path("/custom/plugins")
        registry = PluginRegistry(plugin_dir=custom_dir)
        assert registry.plugin_dir == custom_dir

    def test_empty_registry(self) -> None:
        """Test empty registry state."""
        registry = PluginRegistry()
        assert len(registry) == 0
        assert "nonexistent" not in registry

    def test_register_plugin(self) -> None:
        """Test manual plugin registration."""
        registry = PluginRegistry()
        plugin = SamplePanePlugin()

        registry.register(plugin)

        assert len(registry) == 1
        assert "sample_pane" in registry

    def test_register_duplicate_raises(self) -> None:
        """Test registering duplicate plugin raises error."""
        registry = PluginRegistry()
        plugin1 = SamplePanePlugin()
        plugin2 = SamplePanePlugin()

        registry.register(plugin1)

        with pytest.raises(PluginConflictError, match="sample_pane"):
            registry.register(plugin2)

    def test_get_plugin(self) -> None:
        """Test getting plugin by name."""
        registry = PluginRegistry()
        plugin = SamplePanePlugin()
        registry.register(plugin)

        result = registry.get("sample_pane")
        assert result is plugin

    def test_get_nonexistent_raises(self) -> None:
        """Test getting nonexistent plugin raises error."""
        registry = PluginRegistry()

        with pytest.raises(PluginNotFoundError, match="nonexistent"):
            registry.get("nonexistent")

    def test_get_pane(self) -> None:
        """Test getting pane plugin specifically."""
        registry = PluginRegistry()
        plugin = SamplePanePlugin()
        registry.register(plugin)

        result = registry.get_pane("sample_pane")
        assert result is plugin
        assert isinstance(result, PanePlugin)

    def test_unregister(self) -> None:
        """Test unregistering a plugin."""
        registry = PluginRegistry()
        plugin = SamplePanePlugin()
        registry.register(plugin)

        registry.unregister("sample_pane")

        assert len(registry) == 0
        assert "sample_pane" not in registry

    def test_unregister_nonexistent_raises(self) -> None:
        """Test unregistering nonexistent plugin raises error."""
        registry = PluginRegistry()

        with pytest.raises(PluginNotFoundError):
            registry.unregister("nonexistent")

    def test_unregister_calls_shutdown(self) -> None:
        """Test unregistering calls plugin shutdown."""
        registry = PluginRegistry()
        plugin = SamplePanePlugin()
        plugin.initialize()
        registry.register(plugin)

        assert plugin._initialized is True

        registry.unregister("sample_pane")

        assert plugin._initialized is False

    def test_get_plugins_by_type(self) -> None:
        """Test getting plugins filtered by type."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())
        registry.register(AnotherPanePlugin())

        panes = registry.get_plugins_by_type(PluginType.PANE)

        assert len(panes) == 2
        assert all(isinstance(p, PanePlugin) for p in panes)

    def test_get_all_metadata(self) -> None:
        """Test getting all plugin metadata."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())
        registry.register(AnotherPanePlugin())

        metadata = registry.get_all_metadata()

        assert len(metadata) == 2
        names = [m.name for m in metadata]
        assert "sample_pane" in names
        assert "another_pane" in names

    def test_get_enabled_plugins(self) -> None:
        """Test getting only enabled plugins."""
        registry = PluginRegistry()
        plugin1 = SamplePanePlugin()
        plugin2 = AnotherPanePlugin()
        plugin2.enabled = False

        registry.register(plugin1)
        registry.register(plugin2)

        enabled = registry.get_enabled_plugins()

        assert len(enabled) == 1
        assert enabled[0].name == "sample_pane"

    def test_initialize_all(self) -> None:
        """Test initializing all plugins with config."""
        registry = PluginRegistry()
        plugin1 = SamplePanePlugin()
        plugin2 = AnotherPanePlugin()

        registry.register(plugin1)
        registry.register(plugin2)

        config = {
            "sample_pane": {"option": "value1"},
            "another_pane": {"option": "value2"},
        }
        registry.initialize_all(config)

        assert plugin1._initialized is True
        assert plugin1.config == {"option": "value1"}
        assert plugin2._initialized is True
        assert plugin2.config == {"option": "value2"}

    def test_shutdown_all(self) -> None:
        """Test shutting down all plugins."""
        registry = PluginRegistry()
        plugin1 = SamplePanePlugin()
        plugin2 = AnotherPanePlugin()

        registry.register(plugin1)
        registry.register(plugin2)
        registry.initialize_all()
        registry.shutdown_all()

        assert plugin1._initialized is False
        assert plugin2._initialized is False

    def test_discover_empty_directory(self, tmp_path: Path) -> None:
        """Test discovery with empty plugin directory."""
        registry = PluginRegistry(plugin_dir=tmp_path)
        discovered = registry.discover_all()

        # Should only find entry points (none in test environment)
        assert isinstance(discovered, list)

    def test_discover_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test discovery with nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        registry = PluginRegistry(plugin_dir=nonexistent)

        # Should not raise, just return empty
        discovered = registry.discover_all()
        assert isinstance(discovered, list)


class TestPluginDiscoveryFromDirectory:
    """Tests for directory-based plugin discovery."""

    def test_discover_plugin_from_file(self, tmp_path: Path) -> None:
        """Test discovering a plugin from a .py file."""
        plugin_code = """
from typing import Any
from pydantic import BaseModel
from uptop.models import MetricData
from uptop.plugin_api import PanePlugin


class TestData(MetricData):
    test_value: str = "test"


class DirectoryTestPlugin(PanePlugin):
    name = "directory_test"
    display_name = "Directory Test Plugin"

    async def collect_data(self) -> TestData:
        return TestData(source="test")

    def render_tui(self, data: MetricData) -> Any:
        return None

    def get_schema(self) -> type[BaseModel]:
        return TestData
"""
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(plugin_code)

        registry = PluginRegistry(plugin_dir=tmp_path)
        discovered = registry.discover_all()

        # Should have found our plugin
        names = [m.name for m in discovered]
        assert "directory_test" in names

    def test_skip_underscore_files(self, tmp_path: Path) -> None:
        """Test that files starting with _ are skipped."""
        plugin_file = tmp_path / "_private_plugin.py"
        plugin_file.write_text("# This should be skipped")

        registry = PluginRegistry(plugin_dir=tmp_path)
        discovered = registry.discover_all()

        # Should not have loaded the _private file
        assert all("_private" not in m.name for m in discovered)

    def test_handle_invalid_plugin_file(self, tmp_path: Path) -> None:
        """Test graceful handling of invalid plugin files."""
        invalid_file = tmp_path / "invalid_plugin.py"
        invalid_file.write_text("this is not valid python {{{")

        registry = PluginRegistry(plugin_dir=tmp_path)
        # Should not raise, just log error
        discovered = registry.discover_all()
        assert isinstance(discovered, list)

        # Should have recorded the failure
        assert len(registry.failed_plugins) > 0

    def test_discover_plugin_package(self, tmp_path: Path) -> None:
        """Test discovering a plugin from a subdirectory package."""
        # Create a package directory with __init__.py
        package_dir = tmp_path / "my_plugin"
        package_dir.mkdir()

        plugin_code = """
from typing import Any
from pydantic import BaseModel
from uptop.models import MetricData
from uptop.plugin_api import PanePlugin


class PackageData(MetricData):
    pkg_value: str = "pkg"


class PackagePlugin(PanePlugin):
    name = "package_plugin"
    display_name = "Package Plugin"

    async def collect_data(self) -> PackageData:
        return PackageData(source="package")

    def render_tui(self, data: MetricData) -> Any:
        return None

    def get_schema(self) -> type[BaseModel]:
        return PackageData
"""
        init_file = package_dir / "__init__.py"
        init_file.write_text(plugin_code)

        registry = PluginRegistry(plugin_dir=tmp_path)
        discovered = registry.discover_all()

        names = [m.name for m in discovered]
        assert "package_plugin" in names

    def test_strict_mode_raises_on_error(self, tmp_path: Path) -> None:
        """Test that strict mode raises exceptions instead of logging."""
        invalid_file = tmp_path / "bad_plugin.py"
        invalid_file.write_text("this is not valid python {{{")

        registry = PluginRegistry(plugin_dir=tmp_path)

        with pytest.raises(PluginLoadError):
            registry.discover_all(strict=True)


class TestPluginLifecycle:
    """Tests for plugin lifecycle management."""

    def test_lifecycle_methods_called(self) -> None:
        """Test that lifecycle methods are called in order."""
        registry = PluginRegistry()
        plugin = PluginWithLifecycle()
        registry.register(plugin)

        # Initialize
        registry.initialize_all()
        assert plugin._initialized is True

        # Start
        registry.start_all()
        assert plugin.started is True

        # Stop
        registry.stop_all()
        assert plugin.stopped is True

        # Shutdown
        registry.shutdown_all()
        assert plugin._initialized is False

    def test_dependency_injection(self) -> None:
        """Test that dependencies are injected during initialization."""
        registry = PluginRegistry()
        plugin = PluginWithLifecycle()
        registry.register(plugin)

        dependencies = {"app": "mock_app", "scheduler": "mock_scheduler"}
        registry.initialize_all(dependencies=dependencies)

        assert len(plugin.inject_calls) == 1
        assert plugin.inject_calls[0] == dependencies

    def test_initialize_all_returns_failed(self) -> None:
        """Test that initialize_all returns list of failed plugins."""
        registry = PluginRegistry()
        good_plugin = SamplePanePlugin()
        bad_plugin = FailingPlugin()

        registry.register(good_plugin)
        registry.register(bad_plugin)

        failed = registry.initialize_all()

        assert "failing_plugin" in failed
        assert "sample_pane" not in failed
        assert bad_plugin.enabled is False
        assert good_plugin.enabled is True

    def test_start_skips_disabled_plugins(self) -> None:
        """Test that start_all skips disabled plugins."""
        registry = PluginRegistry()
        plugin = PluginWithLifecycle()
        plugin.enabled = False
        registry.register(plugin)
        registry.initialize_all()

        registry.start_all()

        assert plugin.started is False

    def test_stop_all_in_reverse_order(self) -> None:
        """Test that stop_all processes plugins in reverse order."""
        registry = PluginRegistry()
        call_order: list[str] = []

        # Create two plugins that track stop calls
        class Plugin1(PluginWithLifecycle):
            name = "plugin1"
            display_name = "Plugin 1"

            def stop(self) -> None:
                call_order.append("plugin1")

        class Plugin2(PluginWithLifecycle):
            name = "plugin2"
            display_name = "Plugin 2"

            def stop(self) -> None:
                call_order.append("plugin2")

        registry.register(Plugin1())
        registry.register(Plugin2())
        registry.initialize_all()
        registry.start_all()
        registry.stop_all()

        # Should be in reverse order (plugin2 registered last, stopped first)
        assert call_order == ["plugin2", "plugin1"]

    def test_shutdown_stops_if_running(self) -> None:
        """Test that shutdown_all calls stop_all if plugins are running."""
        registry = PluginRegistry()
        plugin = PluginWithLifecycle()
        registry.register(plugin)
        registry.initialize_all()
        registry.start_all()

        assert plugin.started is True
        assert plugin.stopped is False

        registry.shutdown_all()

        assert plugin.stopped is True
        assert plugin._initialized is False

    def test_is_initialized_property(self) -> None:
        """Test the is_initialized property."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())

        assert registry.is_initialized is False
        registry.initialize_all()
        assert registry.is_initialized is True
        registry.shutdown_all()
        assert registry.is_initialized is False

    def test_is_started_property(self) -> None:
        """Test the is_started property."""
        registry = PluginRegistry()
        plugin = PluginWithLifecycle()
        registry.register(plugin)
        registry.initialize_all()

        assert registry.is_started is False
        registry.start_all()
        assert registry.is_started is True
        registry.stop_all()
        assert registry.is_started is False


class TestPluginTypeAccessors:
    """Tests for type-specific plugin accessors."""

    def test_get_collector(self) -> None:
        """Test getting a collector plugin by name."""
        registry = PluginRegistry()
        plugin = SampleCollectorPlugin()
        registry.register(plugin)

        result = registry.get_collector("sample_collector")
        assert result is plugin
        assert isinstance(result, CollectorPlugin)

    def test_get_collector_wrong_type_raises(self) -> None:
        """Test that get_collector raises for non-collector."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())

        with pytest.raises(PluginNotFoundError, match="not a CollectorPlugin"):
            registry.get_collector("sample_pane")

    def test_get_formatter(self) -> None:
        """Test getting a formatter plugin by name."""
        registry = PluginRegistry()
        plugin = SampleFormatterPlugin()
        registry.register(plugin)

        result = registry.get_formatter("sample_formatter")
        assert result is plugin
        assert isinstance(result, FormatterPlugin)

    def test_get_formatter_wrong_type_raises(self) -> None:
        """Test that get_formatter raises for non-formatter."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())

        with pytest.raises(PluginNotFoundError, match="not a FormatterPlugin"):
            registry.get_formatter("sample_pane")

    def test_get_action(self) -> None:
        """Test getting an action plugin by name."""
        registry = PluginRegistry()
        plugin = SampleActionPlugin()
        registry.register(plugin)

        result = registry.get_action("sample_action")
        assert result is plugin
        assert isinstance(result, ActionPlugin)

    def test_get_action_wrong_type_raises(self) -> None:
        """Test that get_action raises for non-action."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())

        with pytest.raises(PluginNotFoundError, match="not an ActionPlugin"):
            registry.get_action("sample_pane")


class TestRegistryUtilities:
    """Tests for registry utility methods."""

    def test_clear(self) -> None:
        """Test clearing the registry."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())
        registry.register(AnotherPanePlugin())
        registry.initialize_all()

        registry.clear()

        assert len(registry) == 0
        assert registry.is_initialized is False

    def test_iter(self) -> None:
        """Test iterating over plugin names."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())
        registry.register(AnotherPanePlugin())

        names = list(registry)

        assert "sample_pane" in names
        assert "another_pane" in names

    def test_repr(self) -> None:
        """Test string representation."""
        registry = PluginRegistry()
        registry.register(SamplePanePlugin())
        registry.initialize_all()

        repr_str = repr(registry)

        assert "PluginRegistry" in repr_str
        assert "plugins=1" in repr_str
        assert "initialized=True" in repr_str

    def test_failed_plugins_property(self) -> None:
        """Test the failed_plugins property returns a copy."""
        registry = PluginRegistry()
        registry.register(FailingPlugin())
        registry.initialize_all()

        failed1 = registry.failed_plugins
        failed2 = registry.failed_plugins

        assert failed1 == failed2
        assert failed1 is not failed2  # Should be a copy
