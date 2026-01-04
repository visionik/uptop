"""Tests for uptop plugin API."""

from typing import Any
from unittest.mock import MagicMock

from pydantic import BaseModel
import pytest

from uptop.models import MetricData, PluginType
from uptop.plugin_api import (
    API_VERSION,
    ActionPlugin,
    CollectorPlugin,
    FormatterPlugin,
    PanePlugin,
    PluginBase,
)


class TestAPIVersion:
    """Tests for API version."""

    def test_api_version_format(self) -> None:
        """Test API version is in expected format."""
        assert isinstance(API_VERSION, str)
        parts = API_VERSION.split(".")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)


class TestPluginBase:
    """Tests for PluginBase abstract class."""

    def test_default_attributes(self) -> None:
        """Test default class attributes."""

        # Create a concrete subclass for testing
        class TestPlugin(PluginBase):
            name = "test_plugin"
            display_name = "Test Plugin"

            @classmethod
            def get_plugin_type(cls) -> PluginType:
                return PluginType.PANE

        plugin = TestPlugin()
        assert plugin.name == "test_plugin"
        assert plugin.display_name == "Test Plugin"
        assert plugin.version == "0.1.0"
        assert plugin.api_version == API_VERSION
        assert plugin.enabled is True
        assert plugin._initialized is False

    def test_initialize(self) -> None:
        """Test plugin initialization."""

        class TestPlugin(PluginBase):
            name = "test"
            display_name = "Test"

            @classmethod
            def get_plugin_type(cls) -> PluginType:
                return PluginType.PANE

        plugin = TestPlugin()
        plugin.initialize({"key": "value"})

        assert plugin._initialized is True
        assert plugin.config == {"key": "value"}

    def test_shutdown(self) -> None:
        """Test plugin shutdown."""

        class TestPlugin(PluginBase):
            name = "test"
            display_name = "Test"

            @classmethod
            def get_plugin_type(cls) -> PluginType:
                return PluginType.PANE

        plugin = TestPlugin()
        plugin.initialize()
        plugin.shutdown()

        assert plugin._initialized is False

    def test_get_metadata(self) -> None:
        """Test metadata generation."""

        class TestPlugin(PluginBase):
            name = "my_plugin"
            display_name = "My Plugin"
            version = "1.2.3"
            description = "A test plugin"
            author = "Test Author"

            @classmethod
            def get_plugin_type(cls) -> PluginType:
                return PluginType.COLLECTOR

        meta = TestPlugin.get_metadata()

        assert meta.name == "my_plugin"
        assert meta.display_name == "My Plugin"
        assert meta.version == "1.2.3"
        assert meta.plugin_type == PluginType.COLLECTOR
        assert meta.description == "A test plugin"
        assert meta.author == "Test Author"

    def test_get_ai_help_docs_default(self) -> None:
        """Test default AI help docs."""

        class TestPlugin(PluginBase):
            name = "test"
            display_name = "Test Plugin"
            description = "A helpful plugin"

            @classmethod
            def get_plugin_type(cls) -> PluginType:
                return PluginType.PANE

        plugin = TestPlugin()
        docs = plugin.get_ai_help_docs()

        assert "Test Plugin" in docs
        assert "A helpful plugin" in docs


class TestPanePlugin:
    """Tests for PanePlugin abstract class."""

    def test_plugin_type(self) -> None:
        """Test PanePlugin returns PANE type."""
        assert PanePlugin.get_plugin_type() == PluginType.PANE

    def test_default_refresh_interval(self) -> None:
        """Test default refresh interval."""
        assert PanePlugin.default_refresh_interval == 1.0

    def test_abstract_methods_required(self) -> None:
        """Test that abstract methods must be implemented."""

        # This should raise TypeError when instantiated without implementations
        class IncompletePanePlugin(PanePlugin):
            name = "incomplete"
            display_name = "Incomplete"

        with pytest.raises(TypeError):
            IncompletePanePlugin()

    def test_complete_implementation(self) -> None:
        """Test a complete PanePlugin implementation."""

        class TestData(MetricData):
            value: float = 0.0

        class CompletePanePlugin(PanePlugin):
            name = "complete_pane"
            display_name = "Complete Pane"

            async def collect_data(self) -> TestData:
                return TestData(value=42.0, source="test")

            def render_tui(self, data: MetricData) -> Any:
                return MagicMock()  # Mock widget

            def get_schema(self) -> type[BaseModel]:
                return TestData

        plugin = CompletePanePlugin()
        assert plugin.name == "complete_pane"
        assert plugin.get_schema() == TestData


class TestCollectorPlugin:
    """Tests for CollectorPlugin abstract class."""

    def test_plugin_type(self) -> None:
        """Test CollectorPlugin returns COLLECTOR type."""
        assert CollectorPlugin.get_plugin_type() == PluginType.COLLECTOR

    def test_target_pane_default(self) -> None:
        """Test default target_pane is empty."""
        assert CollectorPlugin.target_pane == ""

    def test_complete_implementation(self) -> None:
        """Test a complete CollectorPlugin implementation."""

        class TestCollector(CollectorPlugin):
            name = "test_collector"
            display_name = "Test Collector"
            target_pane = "process"

            def collect(self, context: Any) -> dict[str, Any]:
                return {"extra_field": "extra_value"}

        plugin = TestCollector()
        result = plugin.collect(None)

        assert result == {"extra_field": "extra_value"}
        assert plugin.target_pane == "process"


class TestFormatterPlugin:
    """Tests for FormatterPlugin abstract class."""

    def test_plugin_type(self) -> None:
        """Test FormatterPlugin returns FORMATTER type."""
        assert FormatterPlugin.get_plugin_type() == PluginType.FORMATTER

    def test_defaults(self) -> None:
        """Test default class attributes."""
        assert FormatterPlugin.format_name == ""
        assert FormatterPlugin.cli_flag == ""
        assert FormatterPlugin.file_extension == ".txt"

    def test_complete_implementation(self) -> None:
        """Test a complete FormatterPlugin implementation."""

        class TestFormatter(FormatterPlugin):
            name = "test_formatter"
            display_name = "Test Formatter"
            format_name = "test"
            cli_flag = "--test"
            file_extension = ".test"

            def format(self, data: dict[str, Any]) -> str:
                return f"formatted: {data}"

        plugin = TestFormatter()
        result = plugin.format({"key": "value"})

        assert "formatted:" in result
        assert plugin.format_name == "test"
        assert plugin.cli_flag == "--test"


class TestActionPlugin:
    """Tests for ActionPlugin abstract class."""

    def test_plugin_type(self) -> None:
        """Test ActionPlugin returns ACTION type."""
        assert ActionPlugin.get_plugin_type() == PluginType.ACTION

    def test_defaults(self) -> None:
        """Test default class attributes."""
        assert ActionPlugin.keyboard_shortcut == ""
        assert ActionPlugin.requires_confirmation is False
        assert ActionPlugin.description_short == ""

    def test_complete_implementation(self) -> None:
        """Test a complete ActionPlugin implementation."""

        class TestAction(ActionPlugin):
            name = "test_action"
            display_name = "Test Action"
            keyboard_shortcut = "t"
            requires_confirmation = True

            def can_execute(self, context: Any) -> bool:
                return context is not None

            async def execute(self, context: Any) -> Any:
                return {"success": True}

        plugin = TestAction()

        assert plugin.can_execute(None) is False
        assert plugin.can_execute("something") is True
        assert plugin.keyboard_shortcut == "t"
        assert plugin.requires_confirmation is True
