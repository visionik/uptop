"""Tests for UX Polish features (Phase 9.3).

This module tests:
- Startup improvements (loading screen, lazy loading)
- Smooth transitions and animations
- Visual improvements (spacing, borders, colors)
- Keyboard navigation polish
"""

from __future__ import annotations

import pytest

from uptop.plugins.lazy_loader import (
    DEFERRABLE_PLUGINS,
    ESSENTIAL_PLUGINS,
    LazyModuleLoader,
    LazyPluginFactory,
    create_deferred_plugin_factories,
    create_essential_plugin_factories,
)
from uptop.tui.screens.loading import LoadingMessage, LoadingScreen
from uptop.tui.widgets.pane_container import (
    DATA_HIGHLIGHT_DURATION,
    LOADING_SPINNER_FADE,
    LoadingOverlay,
    PaneContainer,
    PaneState,
)


class TestLazyLoader:
    """Tests for lazy loading utilities."""

    def test_lazy_module_loader_not_loaded_initially(self) -> None:
        """Test that modules are not loaded initially."""
        loader = LazyModuleLoader("os")
        assert not loader.is_loaded

    def test_lazy_module_loader_loads_on_access(self) -> None:
        """Test that modules load when accessed."""
        loader = LazyModuleLoader("os")
        # Access the module
        module = loader.load()
        assert loader.is_loaded
        assert module is not None

    def test_lazy_module_loader_getattr(self) -> None:
        """Test that getattr loads and accesses module."""
        loader = LazyModuleLoader("os")
        # Access attribute through loader
        path_module = loader.path
        assert loader.is_loaded
        assert path_module is not None

    def test_lazy_plugin_factory_not_instantiated_initially(self) -> None:
        """Test that plugins are not instantiated initially."""
        factory = LazyPluginFactory("uptop.plugins.cpu", "CPUPane")
        assert not factory.is_instantiated

    def test_essential_plugins_defined(self) -> None:
        """Test that essential plugins are properly defined."""
        assert "cpu" in ESSENTIAL_PLUGINS
        assert "memory" in ESSENTIAL_PLUGINS
        assert "processes" in ESSENTIAL_PLUGINS

    def test_deferrable_plugins_defined(self) -> None:
        """Test that deferrable plugins are properly defined."""
        assert "network" in DEFERRABLE_PLUGINS
        assert "disk" in DEFERRABLE_PLUGINS

    def test_create_essential_plugin_factories(self) -> None:
        """Test creating essential plugin factories."""
        factories = create_essential_plugin_factories()
        assert "cpu" in factories
        assert "memory" in factories
        assert "processes" in factories

    def test_create_deferred_plugin_factories(self) -> None:
        """Test creating deferred plugin factories."""
        factories = create_deferred_plugin_factories()
        assert "network" in factories
        assert "disk" in factories


class TestLoadingScreen:
    """Tests for loading screen functionality."""

    def test_loading_screen_initial_message(self) -> None:
        """Test loading screen has initial message."""
        screen = LoadingScreen(message="Initializing...")
        assert screen._message == "Initializing..."

    def test_loading_message_widget(self) -> None:
        """Test LoadingMessage widget initialization."""
        msg = LoadingMessage(title="uptop", subtitle="Loading...")
        assert msg._title == "uptop"
        assert msg._subtitle == "Loading..."


class TestPaneContainerAnimations:
    """Tests for pane container animation features."""

    def test_animation_constants_defined(self) -> None:
        """Test that animation constants are defined."""
        assert LOADING_SPINNER_FADE > 0
        assert DATA_HIGHLIGHT_DURATION > 0

    def test_loading_overlay_class(self) -> None:
        """Test LoadingOverlay widget exists."""
        overlay = LoadingOverlay()
        assert overlay is not None

    def test_pane_state_enum(self) -> None:
        """Test PaneState enum values."""
        assert PaneState.NORMAL.value == "normal"
        assert PaneState.LOADING.value == "loading"
        assert PaneState.ERROR.value == "error"
        assert PaneState.STALE.value == "stale"

    def test_pane_container_has_loading_methods(self) -> None:
        """Test that PaneContainer has loading animation methods."""
        container = PaneContainer(title="Test")
        assert hasattr(container, "start_loading")
        assert hasattr(container, "stop_loading")
        assert hasattr(container, "_flash_data_updated")
        assert hasattr(container, "_remove_data_highlight")


class TestHelpScreenBindings:
    """Tests for help screen keybinding display."""

    def test_help_screen_imports(self) -> None:
        """Test that HelpScreen can be imported."""
        from uptop.tui.screens.help import HelpScreen

        assert HelpScreen is not None

    def test_help_screen_bindings(self) -> None:
        """Test that HelpScreen has dismiss bindings."""
        from uptop.tui.screens.help import HelpScreen

        screen = HelpScreen()
        binding_keys = [b.key for b in screen.BINDINGS]
        assert "escape" in binding_keys
        assert "?" in binding_keys


class TestGridLayoutNavigation:
    """Tests for grid layout keyboard navigation."""

    def test_grid_layout_has_focus_actions(self) -> None:
        """Test that GridLayout has number key focus actions."""
        from uptop.tui.layouts.grid import GridLayout

        layout = GridLayout()
        assert hasattr(layout, "action_focus_pane_1")
        assert hasattr(layout, "action_focus_pane_2")
        assert hasattr(layout, "action_focus_pane_3")
        assert hasattr(layout, "action_focus_pane_4")
        assert hasattr(layout, "action_focus_pane_5")

    def test_grid_layout_bindings(self) -> None:
        """Test that GridLayout has correct bindings."""
        from uptop.tui.layouts.grid import GridLayout

        binding_keys = [b.key for b in GridLayout.BINDINGS]
        assert "tab" in binding_keys
        assert "shift+tab" in binding_keys
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "3" in binding_keys


class TestThemeEnhancements:
    """Tests for theme visual enhancements."""

    def test_theme_css_has_focus_styles(self) -> None:
        """Test that generated theme CSS includes focus styles."""
        from uptop.tui.themes.base import generate_theme_css
        from uptop.tui.themes.dark import DARK_THEME

        css = generate_theme_css(DARK_THEME)
        assert "*:focus" in css
        assert "border: double" in css

    def test_theme_css_has_loading_styles(self) -> None:
        """Test that generated theme CSS includes loading state styles."""
        from uptop.tui.themes.base import generate_theme_css
        from uptop.tui.themes.dark import DARK_THEME

        css = generate_theme_css(DARK_THEME)
        assert ".loading-state" in css or "loading" in css.lower()

    def test_theme_css_has_data_updated_styles(self) -> None:
        """Test that generated theme CSS includes data update highlight."""
        from uptop.tui.themes.base import generate_theme_css
        from uptop.tui.themes.dark import DARK_THEME

        css = generate_theme_css(DARK_THEME)
        assert ".data-updated" in css


class TestAppAnimations:
    """Tests for app-level animation features."""

    def test_animation_constants_in_app(self) -> None:
        """Test that animation constants are defined in app."""
        from uptop.tui.app import FADE_IN_DURATION, PROGRESS_ANIMATION_DURATION

        assert FADE_IN_DURATION > 0
        assert PROGRESS_ANIMATION_DURATION > 0

    def test_app_has_startup_animation_method(self) -> None:
        """Test that UptopApp has startup animation method."""
        from uptop.tui.app import UptopApp

        app = UptopApp()
        assert hasattr(app, "_apply_startup_animation")
