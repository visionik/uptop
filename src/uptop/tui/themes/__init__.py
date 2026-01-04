"""Theme module for uptop TUI.

This module provides:
- Theme dataclasses and color definitions
- Built-in themes (dark, light, solarized, nord, gruvbox)
- Theme loading from configuration
- CSS generation for Textual theming

Available themes:
- dark: Default dark theme with comfortable contrast
- light: Light theme for bright environments
- solarized: Classic Solarized dark theme
- nord: Arctic, north-bluish color palette
- gruvbox: Retro groove with warm colors
"""

from typing import TYPE_CHECKING

from uptop.tui.themes.base import Theme, ThemeColors, generate_theme_css
from uptop.tui.themes.dark import DARK_THEME
from uptop.tui.themes.gruvbox import GRUVBOX_THEME
from uptop.tui.themes.light import LIGHT_THEME
from uptop.tui.themes.nord import NORD_THEME
from uptop.tui.themes.solarized import SOLARIZED_THEME

if TYPE_CHECKING:
    from uptop.config import Config

# Registry of all available themes
_THEMES: dict[str, Theme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "solarized": SOLARIZED_THEME,
    "nord": NORD_THEME,
    "gruvbox": GRUVBOX_THEME,
}

# Default theme name when requested theme is not found
DEFAULT_THEME_NAME = "dark"

# List of available theme names for configuration validation
AVAILABLE_THEMES: list[str] = list(_THEMES.keys())


def get_theme(name: str) -> Theme:
    """Get a theme by name.

    Retrieves a theme from the theme registry. If the requested theme
    is not found, falls back to the default dark theme.

    Args:
        name: Name of the theme to retrieve

    Returns:
        Theme object for the requested theme, or dark theme as fallback
    """
    theme = _THEMES.get(name)
    if theme is None:
        # Fall back to default theme
        return _THEMES[DEFAULT_THEME_NAME]
    return theme


def get_theme_css(name: str) -> str:
    """Get CSS for a theme by name.

    Retrieves the theme and generates Textual CSS for it.
    Falls back to dark theme if the requested theme is not found.

    Args:
        name: Name of the theme to get CSS for

    Returns:
        CSS string for the theme
    """
    theme = get_theme(name)
    return generate_theme_css(theme)


def get_theme_from_config(config: "Config") -> Theme:
    """Get theme based on configuration.

    Reads the theme name from config.tui.theme and returns
    the corresponding theme. Falls back to dark theme if
    the configured theme is not found.

    Args:
        config: Configuration object to read theme from

    Returns:
        Theme object based on configuration
    """
    theme_name = config.tui.theme
    return get_theme(theme_name)


def get_theme_css_from_config(config: "Config") -> str:
    """Get theme CSS based on configuration.

    Reads the theme name from config.tui.theme and returns
    the corresponding CSS. Falls back to dark theme CSS if
    the configured theme is not found.

    Args:
        config: Configuration object to read theme from

    Returns:
        CSS string for the configured theme
    """
    theme = get_theme_from_config(config)
    return generate_theme_css(theme)


def list_themes() -> list[tuple[str, str, str]]:
    """List all available themes.

    Returns:
        List of tuples containing (name, display_name, description)
    """
    return [(t.name, t.display_name, t.description) for t in _THEMES.values()]


def is_valid_theme(name: str) -> bool:
    """Check if a theme name is valid.

    Args:
        name: Theme name to check

    Returns:
        True if the theme exists, False otherwise
    """
    return name in _THEMES


__all__ = [
    # Core types
    "Theme",
    "ThemeColors",
    # Theme instances
    "DARK_THEME",
    "LIGHT_THEME",
    "SOLARIZED_THEME",
    "NORD_THEME",
    "GRUVBOX_THEME",
    # Functions
    "get_theme",
    "get_theme_css",
    "get_theme_from_config",
    "get_theme_css_from_config",
    "generate_theme_css",
    "list_themes",
    "is_valid_theme",
    # Constants
    "AVAILABLE_THEMES",
    "DEFAULT_THEME_NAME",
]
