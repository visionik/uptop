"""Abstract base classes for uptop plugins.

This module defines the plugin interfaces that extensions must implement.
Each plugin type has specific responsibilities:

- PanePlugin: Collects data and renders a TUI pane
- CollectorPlugin: Contributes additional data to existing panes
- FormatterPlugin: Formats system data for CLI output
- ActionPlugin: Executes user-triggered actions

Plugin Lifecycle:
1. Discovery: Plugins found via entry points or directory scanning
2. Registration: Plugin metadata stored in registry
3. Initialization: Plugin.initialize() called with config
4. Runtime: Plugin methods called as needed
5. Shutdown: Plugin.shutdown() called for cleanup
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from uptop.models.base import DisplayMode, MetricData, PluginMetadata, PluginType

if TYPE_CHECKING:
    from textual.widget import Widget

API_VERSION = "1.0"


class PluginBase(ABC):
    """Base class for all uptop plugins.

    Provides common functionality shared by all plugin types including
    lifecycle management, configuration, and metadata.

    Class Attributes:
        name: Unique identifier for this plugin (lowercase, underscores)
        display_name: Human-readable name for UI
        version: Plugin version (semver format)
        api_version: Target uptop plugin API version
        description: Brief description of what this plugin does
        author: Plugin author

    Instance Attributes:
        config: Plugin-specific configuration dict
        enabled: Whether the plugin is currently active
    """

    name: str = "unnamed_plugin"
    display_name: str = "Unnamed Plugin"
    version: str = "0.1.0"
    api_version: str = API_VERSION
    description: str = ""
    author: str = ""

    def __init__(self) -> None:
        """Initialize the plugin with default state."""
        self.config: dict[str, Any] = {}
        self.enabled: bool = True
        self._initialized: bool = False

    @classmethod
    @abstractmethod
    def get_plugin_type(cls) -> PluginType:
        """Return the type of this plugin.

        Must be overridden by subclasses to return the correct type.

        Returns:
            The PluginType enum value for this plugin category
        """
        ...

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Generate metadata for this plugin.

        Returns:
            PluginMetadata instance describing this plugin
        """
        return PluginMetadata(
            name=cls.name,
            display_name=cls.display_name,
            plugin_type=cls.get_plugin_type(),
            version=cls.version,
            api_version=cls.api_version,
            description=cls.description,
            author=cls.author,
            enabled=True,
            entry_point=f"{cls.__module__}:{cls.__name__}",
        )

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with configuration.

        Called once after the plugin is loaded but before any other methods.
        Override this to perform setup that requires configuration.

        Args:
            config: Plugin-specific configuration from uptop config file
        """
        self.config = config or {}
        self._initialized = True

    def shutdown(self) -> None:
        """Clean up plugin resources.

        Called when uptop is shutting down or the plugin is being unloaded.
        Override this to release resources, close connections, etc.
        """
        self._initialized = False

    def get_ai_help_docs(self) -> str:
        """Return markdown documentation for --ai-help output.

        Override this to provide detailed documentation about your plugin
        that will be included in the LLM-digestible help output.

        Returns:
            Markdown-formatted string describing the plugin
        """
        return f"## {self.display_name}\n\n{self.description}\n"


class PanePlugin(PluginBase):
    """Abstract base class for pane plugins.

    Pane plugins create new monitoring panels in the TUI. Each pane:
    - Collects data at a configurable interval
    - Renders that data as a Textual widget
    - Defines a Pydantic schema for its data

    Class Attributes:
        default_refresh_interval: Seconds between data collection (default 1.0)

    Example:
        class CPUPane(PanePlugin):
            name = "cpu"
            display_name = "CPU Monitor"
            default_refresh_interval = 1.0

            async def collect_data(self) -> CPUData:
                # Gather CPU metrics
                return CPUData(...)

            def render_tui(self, data: CPUData, size=None, mode=None) -> Widget:
                # Create Textual widget (size and mode can be used to adapt display)
                return CPUWidget(data)

            def get_schema(self) -> type[CPUData]:
                return CPUData
    """

    default_refresh_interval: float = 1.0

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return PANE plugin type."""
        return PluginType.PANE

    @abstractmethod
    async def collect_data(self) -> MetricData:
        """Collect current data for this pane.

        Called at the configured refresh interval. Should be async to avoid
        blocking the event loop during I/O operations.

        Returns:
            A MetricData subclass instance with current metrics

        Raises:
            Exception: Collection errors are caught and logged by the scheduler
        """
        ...

    @abstractmethod
    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> "Widget":
        """Render collected data as a Textual widget.

        Called after collect_data() to update the TUI display.

        Args:
            data: The MetricData from the most recent collection
            size: Optional tuple of (width, height) in terminal cells for the pane.
                  If None, the plugin should use reasonable defaults.
            mode: Optional DisplayMode (MINIMUM, MEDIUM, MAXIMUM).
                  If None, defaults to MEDIUM behavior.

        Returns:
            A Textual Widget to display in the pane
        """
        ...

    @abstractmethod
    def get_schema(self) -> type[BaseModel]:
        """Return the Pydantic model class for this pane's data.

        Used for validation and JSON schema generation.

        Returns:
            The Pydantic BaseModel subclass used by collect_data()
        """
        ...


class CollectorPlugin(PluginBase):
    """Abstract base class for collector plugins.

    Collector plugins contribute additional data to existing panes.
    For example, adding custom metrics to the process pane.

    Class Attributes:
        target_pane: Name of the pane to contribute data to

    Example:
        class DockerProcessInfo(CollectorPlugin):
            name = "docker_process"
            target_pane = "process"

            def collect(self, context: Any) -> dict[str, Any]:
                # Return additional fields
                return {"container_id": get_container_id(context)}
    """

    target_pane: str = ""

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return COLLECTOR plugin type."""
        return PluginType.COLLECTOR

    @abstractmethod
    def collect(self, context: Any) -> dict[str, Any]:
        """Collect additional data for the target pane.

        Called by the target pane during its data collection.

        Args:
            context: Context object from the target pane (e.g., Process)

        Returns:
            Dictionary of additional fields to merge into pane data
        """
        ...


class FormatterPlugin(PluginBase):
    """Abstract base class for formatter plugins.

    Formatter plugins convert system data to output formats for CLI mode.
    Built-in formatters include JSON, Markdown, and Prometheus.

    Class Attributes:
        format_name: Identifier for this format (e.g., "json", "xml")
        cli_flag: CLI flag to select this format (e.g., "--xml")
        file_extension: Default file extension for this format

    Example:
        class XMLFormatter(FormatterPlugin):
            name = "xml_formatter"
            format_name = "xml"
            cli_flag = "--xml"
            file_extension = ".xml"

            def format(self, data: dict[str, Any]) -> str:
                return dicttoxml(data)
    """

    format_name: str = ""
    cli_flag: str = ""
    file_extension: str = ".txt"

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return FORMATTER plugin type."""
        return PluginType.FORMATTER

    @abstractmethod
    def format(self, data: dict[str, Any]) -> str:
        """Format system data as a string.

        Args:
            data: Dictionary containing SystemSnapshot data

        Returns:
            Formatted string representation of the data
        """
        ...


class ActionPlugin(PluginBase):
    """Abstract base class for action plugins.

    Action plugins provide keyboard-triggered operations in the TUI.
    Examples include killing processes, changing priority, etc.

    Class Attributes:
        keyboard_shortcut: Key to trigger this action (e.g., "k", "ctrl+c")
        requires_confirmation: Whether to prompt before executing
        description_short: Brief description for keybinding hints

    Example:
        class KillProcessAction(ActionPlugin):
            name = "kill_process"
            keyboard_shortcut = "k"
            requires_confirmation = True

            def can_execute(self, context: ActionContext) -> bool:
                return context.selected_process is not None

            async def execute(self, context: ActionContext) -> ActionResult:
                # Perform the action
                return ActionResult(success=True)
    """

    keyboard_shortcut: str = ""
    requires_confirmation: bool = False
    description_short: str = ""

    @classmethod
    def get_plugin_type(cls) -> PluginType:
        """Return ACTION plugin type."""
        return PluginType.ACTION

    @abstractmethod
    def can_execute(self, context: Any) -> bool:
        """Check if this action can execute in the current context.

        Called to determine if the action should be available/enabled.

        Args:
            context: Current UI context (selected pane, process, etc.)

        Returns:
            True if the action can be executed, False otherwise
        """
        ...

    @abstractmethod
    async def execute(self, context: Any) -> Any:
        """Execute the action.

        Called when the user triggers this action and can_execute() is True.
        Should be async to avoid blocking the UI.

        Args:
            context: Current UI context

        Returns:
            Result of the action (format TBD based on action type)
        """
        ...
