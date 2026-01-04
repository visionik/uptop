"""TUI module for uptop.

This module provides:
- UptopApp: Main Textual application
- TUI components and widgets
- run_app: Entry point for launching the TUI
- Theme support for visual customization
- HelpScreen: Modal for displaying keybindings
"""

from uptop.tui.app import (
    MainContent,
    PlaceholderPane,
    TitleBar,
    UptopApp,
    run_app,
)
from uptop.tui.screens import HelpScreen
from uptop.tui.themes import (
    AVAILABLE_THEMES,
    DARK_THEME,
    DEFAULT_THEME_NAME,
    GRUVBOX_THEME,
    LIGHT_THEME,
    NORD_THEME,
    SOLARIZED_THEME,
    Theme,
    ThemeColors,
    generate_theme_css,
    get_theme,
    get_theme_css,
    get_theme_css_from_config,
    get_theme_from_config,
    is_valid_theme,
    list_themes,
)

__all__ = [
    # App components
    "MainContent",
    "PlaceholderPane",
    "TitleBar",
    "UptopApp",
    "run_app",
    # Screens
    "HelpScreen",
    # Theme types
    "Theme",
    "ThemeColors",
    # Theme instances
    "DARK_THEME",
    "LIGHT_THEME",
    "SOLARIZED_THEME",
    "NORD_THEME",
    "GRUVBOX_THEME",
    # Theme functions
    "get_theme",
    "get_theme_css",
    "get_theme_from_config",
    "get_theme_css_from_config",
    "generate_theme_css",
    "list_themes",
    "is_valid_theme",
    # Theme constants
    "AVAILABLE_THEMES",
    "DEFAULT_THEME_NAME",
]
