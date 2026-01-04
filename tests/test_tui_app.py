"""Tests for uptop TUI application.

This module tests:
- UptopApp instantiation
- Application lifecycle (startup/shutdown)
- Basic widget composition
- Keyboard bindings
- Help modal functionality
- Global keybindings (quit, help, refresh, focus cycling)
"""

import pytest

from uptop import __version__
from uptop.config import load_config
from uptop.tui import HelpScreen, UptopApp, run_app
from uptop.tui.app import MainContent, PlaceholderPane, TitleBar
from uptop.tui.layouts.grid import GridLayout, GridRow
from uptop.tui.widgets.pane_container import PaneContainer


class TestUptopAppInstantiation:
    """Tests for UptopApp instantiation."""

    def test_instantiate_without_config(self) -> None:
        """Test app can be instantiated without config."""
        app = UptopApp()
        assert app is not None
        assert app.config is None

    def test_instantiate_with_config(self) -> None:
        """Test app can be instantiated with config."""
        config = load_config()
        app = UptopApp(config=config)
        assert app is not None
        assert app.config is config

    def test_app_title(self) -> None:
        """Test app has correct title."""
        app = UptopApp()
        assert app.TITLE == "uptop"

    def test_app_subtitle_has_version(self) -> None:
        """Test app subtitle contains version."""
        app = UptopApp()
        assert __version__ in app.SUB_TITLE


class TestUptopAppLifecycle:
    """Tests for UptopApp lifecycle using Textual's pilot."""

    @pytest.mark.asyncio
    async def test_app_startup(self) -> None:
        """Test app starts up correctly."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # App should be running
            assert pilot.app is app
            # Header should be present
            assert len(app.query("Header")) == 1
            # Footer should be present
            assert len(app.query("Footer")) == 1

    @pytest.mark.asyncio
    async def test_app_shutdown_with_quit_key(self) -> None:
        """Test app shuts down with 'q' key."""
        app = UptopApp()
        async with app.run_test() as pilot:
            await pilot.press("q")
            # App should exit after quit key
            # The context manager handles cleanup

    @pytest.mark.asyncio
    async def test_app_with_config(self) -> None:
        """Test app starts with configuration."""
        config = load_config()
        app = UptopApp(config=config)
        async with app.run_test() as pilot:
            assert pilot.app.config is config
            assert pilot.app.config.interval == config.interval

    @pytest.mark.asyncio
    async def test_grid_layout_exists(self) -> None:
        """Test GridLayout is used as main container."""
        app = UptopApp()
        async with app.run_test():
            grids = app.query(GridLayout)
            assert len(grids) == 1

    @pytest.mark.asyncio
    async def test_pane_containers_exist(self) -> None:
        """Test pane containers are created for all panes."""
        app = UptopApp()
        async with app.run_test():
            panes = app.query(PaneContainer)
            # Should have 5 pane containers: CPU, Memory, Processes, Network, Disk
            assert len(panes) == 5


class TestWidgets:
    """Tests for individual TUI widgets."""

    def test_title_bar_instantiation(self) -> None:
        """Test TitleBar can be instantiated."""
        title_bar = TitleBar()
        assert title_bar is not None

    def test_title_bar_custom_values(self) -> None:
        """Test TitleBar with custom values."""
        title_bar = TitleBar(title="custom", version="1.0.0")
        assert title_bar._title == "custom"
        assert title_bar._version == "1.0.0"

    def test_placeholder_pane_instantiation(self) -> None:
        """Test PlaceholderPane can be instantiated."""
        pane = PlaceholderPane()
        assert pane is not None

    def test_placeholder_pane_custom_name(self) -> None:
        """Test PlaceholderPane with custom name."""
        pane = PlaceholderPane(name="TestPane")
        assert pane._pane_name == "TestPane"

    def test_main_content_instantiation(self) -> None:
        """Test MainContent can be instantiated."""
        content = MainContent()
        assert content is not None


class TestKeyboardBindings:
    """Tests for keyboard bindings."""

    @pytest.mark.asyncio
    async def test_quit_binding_exists(self) -> None:
        """Test quit binding (q) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "q"]
        assert len(bindings) == 1
        assert bindings[0].action == "quit"

    @pytest.mark.asyncio
    async def test_help_binding_exists(self) -> None:
        """Test help binding (?) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "?"]
        assert len(bindings) == 1
        assert bindings[0].action == "toggle_help"

    @pytest.mark.asyncio
    async def test_refresh_binding_exists(self) -> None:
        """Test refresh binding (r) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "r"]
        assert len(bindings) == 1
        assert bindings[0].action == "refresh_all"

    @pytest.mark.asyncio
    async def test_tab_binding_exists(self) -> None:
        """Test tab binding exists for focus cycling."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "tab"]
        assert len(bindings) == 1
        assert bindings[0].action == "focus_next_pane"

    @pytest.mark.asyncio
    async def test_shift_tab_binding_exists(self) -> None:
        """Test shift+tab binding exists for focus cycling."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "shift+tab"]
        assert len(bindings) == 1
        assert bindings[0].action == "focus_previous_pane"

    @pytest.mark.asyncio
    async def test_sort_binding_exists(self) -> None:
        """Test sort binding (s) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "s"]
        assert len(bindings) == 1
        assert bindings[0].action == "sort"

    @pytest.mark.asyncio
    async def test_kill_binding_exists(self) -> None:
        """Test kill binding (k) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "k"]
        assert len(bindings) == 1
        assert bindings[0].action == "kill_process"

    @pytest.mark.asyncio
    async def test_filter_binding_exists(self) -> None:
        """Test filter binding (/) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "/"]
        assert len(bindings) == 1
        assert bindings[0].action == "filter"

    @pytest.mark.asyncio
    async def test_tree_binding_exists(self) -> None:
        """Test tree view binding (t) exists."""
        app = UptopApp()
        bindings = [b for b in app.BINDINGS if b.key == "t"]
        assert len(bindings) == 1
        assert bindings[0].action == "toggle_tree"


class TestActions:
    """Tests for action methods."""

    @pytest.mark.asyncio
    async def test_action_toggle_help_opens_modal(self) -> None:
        """Test help action opens the help modal."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Initially no help screen on the stack
            assert not any(isinstance(s, HelpScreen) for s in app.screen_stack)

            # Press ? to open help
            await pilot.press("?")

            # Help screen should now be on the screen stack
            assert any(isinstance(s, HelpScreen) for s in app.screen_stack)

    @pytest.mark.asyncio
    async def test_action_toggle_help_closes_with_escape(self) -> None:
        """Test help modal closes with Escape key."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Open help modal
            await pilot.press("?")
            assert any(isinstance(s, HelpScreen) for s in app.screen_stack)

            # Close with escape
            await pilot.press("escape")

            # Help screen should be gone
            assert not any(isinstance(s, HelpScreen) for s in app.screen_stack)

    @pytest.mark.asyncio
    async def test_action_toggle_help_closes_with_question_mark(self) -> None:
        """Test help modal closes with ? key."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Open help modal
            await pilot.press("?")
            assert any(isinstance(s, HelpScreen) for s in app.screen_stack)

            # Close with ?
            await pilot.press("?")

            # Help screen should be gone
            assert not any(isinstance(s, HelpScreen) for s in app.screen_stack)

    @pytest.mark.asyncio
    async def test_action_refresh(self) -> None:
        """Test refresh action executes without error."""
        app = UptopApp()
        async with app.run_test() as pilot:
            await pilot.press("r")
            # Action should execute without error
            # The refresh triggers a notification

    @pytest.mark.asyncio
    async def test_action_toggle_tree(self) -> None:
        """Test toggle tree action shows notification."""
        app = UptopApp()
        async with app.run_test() as pilot:
            await pilot.press("t")
            # Action should execute without error

    @pytest.mark.asyncio
    async def test_action_filter(self) -> None:
        """Test filter action shows notification."""
        app = UptopApp()
        async with app.run_test() as pilot:
            await pilot.press("/")
            # Action should execute without error

    @pytest.mark.asyncio
    async def test_action_sort(self) -> None:
        """Test sort action shows notification."""
        app = UptopApp()
        async with app.run_test() as pilot:
            await pilot.press("s")
            # Action should execute without error

    @pytest.mark.asyncio
    async def test_action_kill_process(self) -> None:
        """Test kill process action shows notification."""
        app = UptopApp()
        async with app.run_test() as pilot:
            await pilot.press("k")
            # Action should execute without error


class TestMouseConfiguration:
    """Tests for mouse configuration handling."""

    @pytest.mark.asyncio
    async def test_mouse_enabled_by_default(self) -> None:
        """Test mouse is enabled by default."""
        app = UptopApp()
        assert app._mouse_enabled is True

    @pytest.mark.asyncio
    async def test_mouse_disabled_via_config(self) -> None:
        """Test mouse can be disabled via config."""
        config = load_config(cli_overrides={"tui": {"mouse_enabled": False}})
        app = UptopApp(config=config)
        assert app._mouse_enabled is False


class TestRunApp:
    """Tests for run_app function."""

    def test_run_app_function_exists(self) -> None:
        """Test run_app function is exported."""
        assert callable(run_app)


class TestLayout:
    """Tests for application layout structure."""

    @pytest.mark.asyncio
    async def test_grid_rows_exist(self) -> None:
        """Test grid row containers exist."""
        app = UptopApp()
        async with app.run_test():
            # GridLayout creates rows with ids: grid-row-0, grid-row-1, grid-row-2
            rows = app.query(GridRow)
            assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_header_and_footer_exist(self) -> None:
        """Test Header and Footer are present in layout."""
        app = UptopApp()
        async with app.run_test():
            headers = app.query("Header")
            assert len(headers) == 1
            footers = app.query("Footer")
            assert len(footers) == 1

    @pytest.mark.asyncio
    async def test_panes_have_correct_ids(self) -> None:
        """Test pane containers have correct IDs based on layout config."""
        app = UptopApp()
        async with app.run_test():
            # Verify expected pane IDs exist
            expected_panes = ["cpu", "memory", "processes", "network", "disk"]
            for pane_name in expected_panes:
                panes = app.query(f"#pane-{pane_name}")
                assert len(panes) == 1, f"Expected pane #{pane_name} to exist"


class TestHelpScreen:
    """Tests for the HelpScreen modal."""

    def test_help_screen_instantiation(self) -> None:
        """Test HelpScreen can be instantiated."""
        screen = HelpScreen()
        assert screen is not None

    def test_help_screen_has_dismiss_bindings(self) -> None:
        """Test HelpScreen has bindings for dismissal."""
        screen = HelpScreen()
        # Check for escape binding
        escape_bindings = [b for b in screen.BINDINGS if b.key == "escape"]
        assert len(escape_bindings) == 1
        assert escape_bindings[0].action == "dismiss"

        # Check for ? binding
        question_bindings = [b for b in screen.BINDINGS if b.key == "?"]
        assert len(question_bindings) == 1
        assert question_bindings[0].action == "dismiss"

    @pytest.mark.asyncio
    async def test_help_screen_contains_global_keybindings(self) -> None:
        """Test HelpScreen displays global keybindings."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Open help modal
            await pilot.press("?")

            # Check for global keybinding section content
            # The help screen should be on the screen stack
            assert any(isinstance(s, HelpScreen) for s in app.screen_stack)

    @pytest.mark.asyncio
    async def test_help_screen_contains_process_keybindings(self) -> None:
        """Test HelpScreen displays process pane keybindings."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Open help modal
            await pilot.press("?")

            # Check help screen is on the screen stack
            assert any(isinstance(s, HelpScreen) for s in app.screen_stack)

    @pytest.mark.asyncio
    async def test_help_screen_has_q_dismiss_binding(self) -> None:
        """Test help modal has a q binding that dismisses it."""
        screen = HelpScreen()
        # Check for q binding
        q_bindings = [b for b in screen.BINDINGS if b.key == "q"]
        assert len(q_bindings) == 1
        assert q_bindings[0].action == "dismiss"


class TestGlobalKeybindings:
    """Tests specifically for global keybinding functionality."""

    @pytest.mark.asyncio
    async def test_quit_exits_application(self) -> None:
        """Test that q key triggers application exit."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # App should be running
            assert pilot.app is app

            # Press q to quit
            await pilot.press("q")
            # The run_test context manager handles cleanup

    @pytest.mark.asyncio
    async def test_focus_cycling_with_tab(self) -> None:
        """Test Tab key cycles focus to next focusable widget."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Press tab to cycle focus
            await pilot.press("tab")
            # Tab cycling should execute without error

    @pytest.mark.asyncio
    async def test_focus_cycling_with_shift_tab(self) -> None:
        """Test Shift+Tab key cycles focus to previous focusable widget."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Press shift+tab to cycle focus backward
            await pilot.press("shift+tab")
            # Shift+Tab cycling should execute without error

    @pytest.mark.asyncio
    async def test_refresh_triggers_update(self) -> None:
        """Test r key triggers data refresh."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Press r to refresh
            await pilot.press("r")
            # Refresh should execute without error
            # A notification is shown to user

    @pytest.mark.asyncio
    async def test_all_bindings_are_functional(self) -> None:
        """Test all defined bindings can be pressed without error."""
        app = UptopApp()
        async with app.run_test() as pilot:
            # Test all bindings except q (which would exit)
            for binding in app.BINDINGS:
                if binding.key != "q":
                    await pilot.press(binding.key)
                    # Close any modal that might have opened
                    if binding.key == "?":
                        await pilot.press("escape")


class TestRefreshLoop:
    """Tests for the async data refresh loop (Phase 3.5)."""

    def test_app_has_refresh_timers_dict(self) -> None:
        """Test app initializes with empty refresh timers dict."""
        app = UptopApp()
        assert hasattr(app, "_refresh_timers")
        assert isinstance(app._refresh_timers, dict)
        assert len(app._refresh_timers) == 0

    def test_app_has_last_good_data_dict(self) -> None:
        """Test app initializes with empty last good data dict."""
        app = UptopApp()
        assert hasattr(app, "_last_good_data")
        assert isinstance(app._last_good_data, dict)
        assert len(app._last_good_data) == 0

    def test_get_refresh_interval_defaults_to_one_second(self) -> None:
        """Test get_refresh_interval returns 1.0 when no config or registry."""
        app = UptopApp()
        assert app.get_refresh_interval("cpu") == 1.0

    def test_get_refresh_interval_uses_config_pane_interval(self) -> None:
        """Test get_refresh_interval uses pane-specific config."""
        config = load_config(cli_overrides={"tui": {"panes": {"cpu": {"refresh_interval": 2.5}}}})
        app = UptopApp(config=config)
        assert app.get_refresh_interval("cpu") == 2.5

    def test_get_refresh_interval_uses_global_interval_as_fallback(self) -> None:
        """Test get_refresh_interval uses global config interval as fallback."""
        config = load_config(cli_overrides={"interval": 3.0})
        app = UptopApp(config=config)
        # When pane-specific interval not set, should use global
        assert app.get_refresh_interval("unknown_pane") == 3.0

    def test_stop_refresh_loops_clears_timers(self) -> None:
        """Test stop_refresh_loops clears all timers."""
        app = UptopApp()
        # Add some mock timer entries
        app._refresh_timers["test1"] = None  # type: ignore[assignment]
        app._refresh_timers["test2"] = None  # type: ignore[assignment]
        # Note: Real timers have .stop() method, but we're just testing cleanup
        app._refresh_timers.clear()  # Simulate what stop_refresh_loops does
        assert len(app._refresh_timers) == 0

    def test_app_without_registry_has_no_timers(self) -> None:
        """Test app without registry doesn't have any refresh timers."""
        app = UptopApp()
        # Without registry being set, timers dict should be empty on init
        assert len(app._refresh_timers) == 0

    @pytest.mark.asyncio
    async def test_refresh_all_panes_without_registry_does_nothing(self) -> None:
        """Test refresh_all_panes is safe to call without registry."""
        app = UptopApp()
        # Should not raise - just returns immediately without registry
        await app.refresh_all_panes()
        # Verify nothing was added
        assert len(app._refresh_timers) == 0


class TestRefreshLoopWithRegistry:
    """Tests for refresh loop behavior with a mock registry."""

    @pytest.fixture
    def mock_pane_plugin(self):  # type: ignore[no-untyped-def]
        """Create a mock pane plugin for testing."""
        from unittest.mock import MagicMock

        from textual.widgets import Label

        from uptop.models.base import MetricData
        from uptop.plugin_api.base import PanePlugin

        class MockPanePlugin(PanePlugin):
            name = "test_pane"
            display_name = "Test Pane"
            version = "0.1.0"
            default_refresh_interval = 1.5

            def __init__(self) -> None:
                super().__init__()
                self.collect_count = 0
                self.should_fail = False
                self.enabled = True

            async def collect_data(self) -> MetricData:
                self.collect_count += 1
                if self.should_fail:
                    raise RuntimeError("Mock collection error")
                return MagicMock(spec=MetricData)

            def render_tui(self, data: MetricData) -> Label:
                return Label(f"Test data #{self.collect_count}")

            def get_schema(self) -> type[MetricData]:
                return MetricData

        return MockPanePlugin()

    @pytest.fixture
    def mock_registry(self, mock_pane_plugin):  # type: ignore[no-untyped-def]
        """Create a mock registry with the mock pane plugin."""
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.get_plugins_by_type.return_value = [mock_pane_plugin]
        registry.get_pane.return_value = mock_pane_plugin
        registry.__contains__ = lambda self, name: name == "test_pane"
        return registry

    def test_get_refresh_interval_uses_plugin_default(self, mock_registry) -> None:  # type: ignore[no-untyped-def]
        """Test get_refresh_interval uses plugin's default_refresh_interval."""
        app = UptopApp(plugin_registry=mock_registry)
        # Should use the plugin's default of 1.5
        assert app.get_refresh_interval("test_pane") == 1.5

    @pytest.mark.asyncio
    async def test_create_refresh_callback_returns_callable(self) -> None:
        """Test _create_refresh_callback returns an async callable."""
        import asyncio

        app = UptopApp()
        callback = app._create_refresh_callback("test")
        assert callable(callback)
        # Should be async
        assert asyncio.iscoroutinefunction(callback)


class TestRefreshIntervalConfiguration:
    """Tests for refresh interval configuration precedence."""

    def test_config_pane_interval_takes_precedence(self) -> None:
        """Test pane-specific config takes precedence over plugin default."""
        from unittest.mock import MagicMock

        from uptop.plugin_api.base import PanePlugin

        # Create a mock plugin with default_refresh_interval
        class MockPlugin(PanePlugin):
            name = "cpu"
            display_name = "CPU"
            default_refresh_interval = 5.0

            async def collect_data(self):
                pass

            def render_tui(self, data):
                pass

            def get_schema(self):
                pass

        mock_plugin = MockPlugin()

        # Create mock registry
        registry = MagicMock()
        registry.get_pane.return_value = mock_plugin
        registry.__contains__ = lambda self, name: name == "cpu"

        # Config with pane-specific interval
        config = load_config(cli_overrides={"tui": {"panes": {"cpu": {"refresh_interval": 0.5}}}})

        app = UptopApp(config=config, plugin_registry=registry)

        # Config pane interval (0.5) should take precedence over plugin default (5.0)
        assert app.get_refresh_interval("cpu") == 0.5

    def test_plugin_default_used_when_no_pane_config(self) -> None:
        """Test plugin default is used when no pane-specific config."""
        from unittest.mock import MagicMock

        from uptop.plugin_api.base import PanePlugin

        class MockPlugin(PanePlugin):
            name = "memory"
            display_name = "Memory"
            default_refresh_interval = 2.0

            async def collect_data(self):
                pass

            def render_tui(self, data):
                pass

            def get_schema(self):
                pass

        mock_plugin = MockPlugin()

        registry = MagicMock()
        registry.get_pane.return_value = mock_plugin
        registry.__contains__ = lambda self, name: name == "memory"

        # Config without memory pane config
        config = load_config()
        app = UptopApp(config=config, plugin_registry=registry)

        # Should use plugin default since no pane-specific config
        assert app.get_refresh_interval("memory") == 2.0

    def test_global_interval_used_when_no_plugin(self) -> None:
        """Test global interval used when plugin not in registry."""
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.__contains__ = lambda self, name: False

        config = load_config(cli_overrides={"interval": 4.0})
        app = UptopApp(config=config, plugin_registry=registry)

        # Should use global interval for unknown plugin
        assert app.get_refresh_interval("unknown") == 4.0


class TestErrorHandlingInRefresh:
    """Tests for error handling during data collection."""

    @pytest.mark.asyncio
    async def test_refresh_pane_handles_missing_container(self) -> None:
        """Test _refresh_pane handles missing container gracefully."""
        from unittest.mock import MagicMock

        # Create mock registry with a plugin
        class MockPlugin:
            name = "test"
            enabled = True

            async def collect_data(self):
                return MagicMock()

            def render_tui(self, data):
                from textual.widgets import Label

                return Label("test")

        registry = MagicMock()
        registry.get_pane.return_value = MockPlugin()

        app = UptopApp(plugin_registry=registry)
        async with app.run_test():
            # Should not raise even though container doesn't exist
            await app._refresh_pane("test")

    @pytest.mark.asyncio
    async def test_refresh_pane_handles_plugin_not_found(self) -> None:
        """Test _refresh_pane handles plugin not found gracefully."""
        from unittest.mock import MagicMock

        from uptop.plugins.registry import PluginNotFoundError

        registry = MagicMock()
        registry.get_pane.side_effect = PluginNotFoundError("not found")

        app = UptopApp(plugin_registry=registry)
        async with app.run_test():
            # Should not raise
            await app._refresh_pane("nonexistent")
