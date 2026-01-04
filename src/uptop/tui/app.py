"""Main TUI application for uptop.

This module provides:
- UptopApp: The main Textual application class
- CSS styling for the application
- Title bar with version display
- Basic screen structure for panes
- Async data refresh loop for pane plugins
- Global keybindings (quit, help, refresh, focus cycling)
- Startup loading screen with animations
- Smooth transitions and visual polish
- Performance profiling integration
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Footer, Header, Label, Static

from uptop import __version__
from uptop.performance import get_profiler
from uptop.tui.layouts.grid import DEFAULT_LAYOUT_CONFIG, GridLayout
from uptop.tui.screens import (
    ConfirmKillScreen,
    FilterScreen,
    HelpScreen,
    KillSignal,
    LoadingScreen,
)

if TYPE_CHECKING:
    from uptop.config import Config
    from uptop.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)

# Animation durations (in seconds)
FADE_IN_DURATION = 0.3
PROGRESS_ANIMATION_DURATION = 0.2


class TitleBar(Static):
    """Title bar widget showing application name and version."""

    DEFAULT_CSS = """
    TitleBar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        text-align: center;
    }
    """

    def __init__(self, title: str = "uptop", version: str = __version__) -> None:
        """Initialize the title bar.

        Args:
            title: Application title to display
            version: Version string to display
        """
        super().__init__()
        self._title = title
        self._version = version

    def compose(self) -> ComposeResult:
        """Compose the title bar content."""
        yield Label(f"{self._title} v{self._version}")


class PlaceholderPane(Static):
    """Placeholder pane widget for development.

    This will be replaced with actual pane widgets in Phase 3.4.
    """

    DEFAULT_CSS = """
    PlaceholderPane {
        border: solid $primary;
        height: 100%;
        width: 100%;
        padding: 1;
    }
    """

    def __init__(self, name: str = "Placeholder") -> None:
        """Initialize placeholder pane.

        Args:
            name: Name to display in the pane
        """
        super().__init__()
        self._pane_name = name

    def compose(self) -> ComposeResult:
        """Compose the placeholder content."""
        yield Label(f"[{self._pane_name}]\n\nPane content will appear here...")


class MainContent(Container):
    """Main content area containing panes."""

    DEFAULT_CSS = """
    MainContent {
        height: 100%;
        width: 100%;
    }
    """


class UptopApp(App[None]):
    """Main uptop TUI application.

    This is the primary Textual application class that manages the
    system monitor TUI. It handles:
    - Application lifecycle (startup, shutdown)
    - Screen layout and composition
    - Keyboard bindings
    - Theme management
    - Pane coordination
    - Async data refresh loop for pane plugins

    Attributes:
        config: The application configuration object
        registry: The plugin registry (optional, for testing)
    """

    TITLE = "uptop"
    SUB_TITLE = f"v{__version__}"

    CSS = """
    Screen {
        layout: vertical;
    }

    Header {
        dock: top;
        height: 1;
        background: $primary;
    }

    Footer {
        dock: bottom;
        height: 1;
    }

    #main-container {
        height: 1fr;
        width: 100%;
    }

    #top-row {
        height: 1fr;
        width: 100%;
    }

    #bottom-row {
        height: 1fr;
        width: 100%;
    }

    .pane {
        border: solid $primary;
        padding: 0 1;
        height: 100%;
    }

    .pane-title {
        text-style: bold;
        color: $text;
    }

    /* Startup fade-in animation */
    .fade-in {
        opacity: 0;
    }

    .fade-in.visible {
        opacity: 1;
    }

    /* Data change highlight effect */
    .data-highlight {
        background: $accent 20%;
    }

    /* Loading spinner for individual panes */
    .pane-loading LoadingIndicator {
        width: 100%;
        height: 100%;
    }

    /* Focus indicator enhancements */
    *:focus {
        border: double $accent;
    }

    /* Keyboard navigation hints in footer */
    Footer {
        background: $surface;
    }

    Footer > .footer--key {
        background: $primary;
        color: $text;
    }

    Footer > .footer--description {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("?", "toggle_help", "Help"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("tab", "focus_next_pane", "Next Pane", show=False),
        Binding("shift+tab", "focus_previous_pane", "Prev Pane", show=False),
        Binding("t", "toggle_tree", "Tree View"),
        Binding("/", "filter", "Filter"),
        Binding("s", "sort", "Sort"),
        Binding("k", "kill_process", "Kill"),
    ]

    def __init__(
        self,
        config: Config | None = None,
        plugin_registry: PluginRegistry | None = None,
        debug_mode: bool = False,
    ) -> None:
        """Initialize the uptop application.

        Args:
            config: Optional configuration object. If not provided,
                   default configuration will be used.
            plugin_registry: Optional plugin registry. If not provided,
                            a new registry will be created.
            debug_mode: Enable performance profiling and debug output.
        """
        super().__init__()
        self._config = config
        self._plugin_registry = plugin_registry
        self._mouse_enabled = True
        self._refresh_timers: dict[str, Timer] = {}
        self._last_good_data: dict[str, Any] = {}
        self._debug_mode = debug_mode

        # Initialize performance profiling if debug mode is enabled
        if debug_mode:
            profiler = get_profiler()
            profiler.enable_all()
            logger.info("Performance profiling enabled")

        if config:
            self._mouse_enabled = config.tui.mouse_enabled

    @property
    def config(self) -> Config | None:
        """Get the application configuration."""
        return self._config

    @property
    def plugin_registry(self) -> PluginRegistry | None:
        """Get the plugin registry."""
        return self._plugin_registry

    @property
    def debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self._debug_mode

    def get_performance_report(self) -> str:
        """Get a formatted performance report.

        Returns:
            Formatted string with performance metrics.
            Returns empty string if debug mode is disabled.
        """
        if not self._debug_mode:
            return "Performance profiling is disabled. Enable with debug_mode=True."

        profiler = get_profiler()
        return profiler.format_report()

    def get_refresh_interval(self, pane_name: str) -> float:
        """Get the refresh interval for a specific pane.

        If a global interval was explicitly set via CLI (-i/--interval),
        that takes precedence for all panes. Otherwise, checks pane-specific
        config, then plugin default, then global default.

        Args:
            pane_name: Name of the pane plugin

        Returns:
            Refresh interval in seconds
        """
        # If global interval was explicitly overridden via CLI, use it for all panes
        if self._config and self._config.interval_override:
            return self._config.interval

        # Check pane-specific config
        if self._config and pane_name in self._config.tui.panes:
            pane_config = self._config.get_pane_config(pane_name)
            return pane_config.refresh_interval

        # Check plugin default
        if self._plugin_registry and pane_name in self._plugin_registry:
            try:
                plugin = self._plugin_registry.get_pane(pane_name)
                return plugin.default_refresh_interval
            except Exception:
                pass

        # Fall back to global interval or default
        if self._config:
            return self._config.interval
        return 1.0

    def compose(self) -> ComposeResult:
        """Compose the main application layout.

        Uses GridLayout with real pane widgets for all system monitors.

        Yields:
            Widgets that make up the application layout
        """
        yield Header(show_clock=True)
        yield GridLayout(config=self._config, layout_config=DEFAULT_LAYOUT_CONFIG)
        yield Footer()

    @property
    def mouse_enabled(self) -> bool:
        """Check if mouse support is enabled.

        Returns:
            True if mouse is enabled, False otherwise
        """
        return self._mouse_enabled

    async def on_mount(self) -> None:
        """Handle application mount event.

        Called when the application is mounted and ready to display.
        Sets up initial state, configuration, and starts refresh loops.
        Includes a brief loading indicator and fade-in effect for polish.
        """
        self.log.info(f"uptop v{__version__} started")
        self.log.info(f"Mouse support: {'enabled' if self._mouse_enabled else 'disabled'}")

        if self._config:
            self.log.info(f"Theme: {self._config.tui.theme}")
            self.log.info(f"Refresh interval: {self._config.interval}s")

        # Apply fade-in animation to main content
        await self._apply_startup_animation()

        # Start refresh loops for all registered pane plugins
        await self._start_refresh_loops()

    async def _apply_startup_animation(self) -> None:
        """Apply startup fade-in animation to the grid layout.

        Creates a smooth visual transition when the app starts.
        """
        try:
            grid = self.query_one(GridLayout)
            # Start with low opacity
            grid.styles.opacity = 0.0
            # Animate to full opacity
            grid.styles.animate(
                "opacity",
                value=1.0,
                duration=FADE_IN_DURATION,
                easing="out_cubic",
            )
        except Exception:
            # If animation fails, ensure content is visible
            pass

    async def _start_refresh_loops(self) -> None:
        """Start refresh loops for all registered pane plugins.

        Each pane gets its own timer based on its configured refresh interval.
        """
        if not self._plugin_registry:
            logger.debug("No registry available, skipping refresh loop setup")
            return

        from uptop.models.base import PluginType

        # Get all pane plugins
        pane_plugins = self._plugin_registry.get_plugins_by_type(PluginType.PANE)

        for plugin in pane_plugins:
            if not plugin.enabled:
                continue

            pane_name = plugin.name
            interval = self.get_refresh_interval(pane_name)

            logger.info(f"Starting refresh loop for {pane_name} at {interval}s interval")

            # Create a timer for this pane
            timer = self.set_interval(
                interval,
                self._create_refresh_callback(pane_name),
                name=f"refresh-{pane_name}",
            )
            self._refresh_timers[pane_name] = timer

            # Do an initial refresh immediately
            self.call_later(self._refresh_pane, pane_name)

    def _create_refresh_callback(self, pane_name: str) -> Any:
        """Create a callback function for refreshing a specific pane.

        This is needed because lambdas capture variables by reference,
        so we need to capture the pane_name by value.

        Args:
            pane_name: Name of the pane to refresh

        Returns:
            Callback function that refreshes the specified pane
        """

        async def refresh_callback() -> None:
            await self._refresh_pane(pane_name)

        return refresh_callback

    async def _refresh_pane(self, pane_name: str) -> None:
        """Refresh a single pane with new data.

        Collects data from the pane plugin and updates the widget.
        Handles errors gracefully by showing stale data indicator.
        Includes optional performance profiling when debug_mode is enabled.

        Args:
            pane_name: Name of the pane to refresh
        """
        if not self._plugin_registry:
            return

        # Import here to avoid circular imports
        from uptop.tui.widgets.pane_container import PaneContainer

        try:
            plugin = self._plugin_registry.get_pane(pane_name)
        except Exception as e:
            logger.error(f"Failed to get pane plugin {pane_name}: {e}")
            return

        # Try to find the pane container
        try:
            container = self.query_one(f"#pane-{pane_name}", PaneContainer)
        except Exception:
            # Container may not exist yet (during initial setup)
            logger.debug(f"Pane container for {pane_name} not found")
            return

        # Start loading indicator
        container.start_loading()

        # Track timing for profiling
        collect_start = time.monotonic()

        try:
            # Collect data asynchronously
            data = await plugin.collect_data()

            # Record collection time if profiling is enabled
            if self._debug_mode:
                collect_time_ms = (time.monotonic() - collect_start) * 1000
                profiler = get_profiler()
                profiler.collector_profiler.record(pane_name, collect_time_ms)

            # Store as last good data
            self._last_good_data[pane_name] = data

            # Time the render
            render_start = time.monotonic()

            # Render the widget
            widget = plugin.render_tui(data)

            # Update the container
            container.set_content(widget)
            container.stop_loading()
            container.clear_error()
            container.mark_fresh()

            # Record render time if profiling is enabled
            if self._debug_mode:
                render_time_ms = (time.monotonic() - render_start) * 1000
                profiler = get_profiler()
                profiler.render_profiler.record_widget(pane_name, render_time_ms)

            logger.debug(f"Refreshed pane {pane_name} successfully")

        except Exception as e:
            logger.error(f"Error refreshing pane {pane_name}: {e}")

            # Stop loading and show error state
            container.stop_loading()
            container.set_error(str(e))

            # Mark data as stale but keep showing last good data
            container.mark_stale()

    async def refresh_all_panes(self) -> None:
        """Refresh all panes immediately.

        This is called when the user presses the refresh key.
        """
        if not self._plugin_registry:
            return

        from uptop.models.base import PluginType

        pane_plugins = self._plugin_registry.get_plugins_by_type(PluginType.PANE)

        for plugin in pane_plugins:
            if plugin.enabled:
                await self._refresh_pane(plugin.name)

    def stop_refresh_loops(self) -> None:
        """Stop all refresh timers.

        Called during shutdown to clean up resources.
        """
        for pane_name, timer in self._refresh_timers.items():
            timer.stop()
            logger.debug(f"Stopped refresh timer for {pane_name}")

        self._refresh_timers.clear()

    async def action_toggle_help(self) -> None:
        """Toggle the help screen modal.

        If the help screen is not currently displayed, show it.
        If already displayed, this will be caught by the HelpScreen's bindings.
        """
        await self.push_screen(HelpScreen())

    async def action_refresh_all(self) -> None:
        """Manually refresh all panes.

        Forces an immediate data collection for all enabled panes,
        bypassing the normal refresh interval timing.
        """
        # Notify user of refresh
        self.notify("Refreshing all panes...", title="Refresh", timeout=1)
        logger.info("Manual refresh triggered for all panes")

        # Trigger immediate refresh for all panes
        await self.refresh_all_panes()

        # Reset timers so they continue from now
        for timer in self._refresh_timers.values():
            timer.reset()

    async def action_focus_next_pane(self) -> None:
        """Focus the next pane in the layout.

        Cycles through focusable panes in tab order.
        """
        self.action_focus_next()

    async def action_focus_previous_pane(self) -> None:
        """Focus the previous pane in the layout.

        Cycles through focusable panes in reverse tab order.
        """
        self.action_focus_previous()

    def _get_process_widget(self) -> Any:
        """Get the ProcessWidget if available.

        Returns:
            ProcessWidget instance or None if not found
        """
        try:
            from uptop.tui.panes.process_widget import ProcessWidget

            return self.query_one(ProcessWidget)
        except Exception:
            return None

    async def action_toggle_tree(self) -> None:
        """Toggle tree view in process pane.

        Switches between flat list view and hierarchical tree view
        showing parent-child process relationships.
        """
        widget = self._get_process_widget()
        if widget:
            widget.toggle_tree_view()
            mode = "tree" if widget.tree_view else "flat"
            self.notify(f"Switched to {mode} view", title="Tree View", timeout=1)
        else:
            self.notify("Process pane not available", title="Tree View")

    @work
    async def action_filter(self) -> None:
        """Open filter dialog for process pane.

        Opens a modal dialog for entering filter text to filter
        processes by name, command, PID, or username.
        """
        widget = self._get_process_widget()
        if widget:
            current_filter = widget.filter_text
            result = await self.push_screen_wait(FilterScreen(current_filter))
            if result is not None:
                widget.set_filter(result)
                if result:
                    self.notify(f"Filter: '{result}'", title="Filter", timeout=1)
                else:
                    self.notify("Filter cleared", title="Filter", timeout=1)
        else:
            self.notify("Process pane not available", title="Filter")

    async def action_sort(self) -> None:
        """Cycle through sort columns in process pane.

        Cycles through: CPU% -> MEM% -> PID -> User -> Command
        """
        widget = self._get_process_widget()
        if widget:
            widget.cycle_sort()
            from uptop.tui.panes.process_widget import COLUMN_CONFIG

            col_name = COLUMN_CONFIG[widget.sort_column][0]
            direction = "desc" if widget.sort_direction.value == "desc" else "asc"
            self.notify(f"Sort: {col_name} ({direction})", title="Sort", timeout=1)
        else:
            self.notify("Process pane not available", title="Sort")

    @work
    async def action_kill_process(self) -> None:
        """Kill the selected process.

        Shows a confirmation dialog before attempting to kill
        the currently selected process in the process pane.
        """
        widget = self._get_process_widget()
        if not widget:
            self.notify("Process pane not available", title="Kill")
            return

        pid = widget.get_selected_pid()
        if pid is None:
            self.notify("No process selected", title="Kill")
            return

        process = widget.get_selected_process()
        result = await self.push_screen_wait(ConfirmKillScreen(pid, process))

        if result and result.confirmed:
            try:
                import os

                os.kill(result.pid, result.signal.value)
                signal_name = "SIGTERM" if result.signal == KillSignal.SIGTERM else "SIGKILL"
                self.notify(
                    f"Sent {signal_name} to process {result.pid}",
                    title="Kill",
                    timeout=2,
                )
                # Trigger a refresh to update the process list
                await self.refresh_all_panes()
            except ProcessLookupError:
                self.notify(
                    f"Process {result.pid} no longer exists",
                    title="Kill",
                    severity="warning",
                )
            except PermissionError:
                self.notify(
                    f"Permission denied to kill process {result.pid}",
                    title="Kill",
                    severity="error",
                )
            except Exception as e:
                self.notify(
                    f"Failed to kill process: {e}",
                    title="Kill",
                    severity="error",
                )


def run_app(config: Config | None = None, debug_mode: bool = False) -> None:
    """Create and run the uptop TUI application.

    This is the main entry point for running the TUI.

    Args:
        config: Optional configuration object
        debug_mode: Enable performance profiling and debug output
    """
    # Import here to avoid circular imports
    from uptop.plugins.registry import PluginRegistry

    # Create plugin registry
    registry = PluginRegistry()

    # Register internal pane plugins
    from uptop.plugins.cpu import CPUPane
    from uptop.plugins.disk import DiskPane
    from uptop.plugins.memory import MemoryPane
    from uptop.plugins.network import NetworkPane
    from uptop.plugins.processes import ProcessPane

    registry.register(CPUPane())
    registry.register(MemoryPane())
    registry.register(ProcessPane())
    registry.register(NetworkPane())
    registry.register(DiskPane())

    # Discover any external plugins
    registry.discover_all()

    # Initialize all pane plugins
    from uptop.models.base import PluginType

    for plugin in registry.get_plugins_by_type(PluginType.PANE):
        try:
            plugin.initialize()
            logger.info(f"Initialized pane plugin: {plugin.name}")
        except Exception as e:
            logger.error(f"Failed to initialize plugin {plugin.name}: {e}")

    app = UptopApp(config=config, plugin_registry=registry, debug_mode=debug_mode)
    app.run()

    # Print performance report if debug mode was enabled
    if debug_mode:
        print("\n" + app.get_performance_report())
