"""Base theme definitions for uptop TUI.

This module provides:
- ThemeColors dataclass for theme color definitions
- Theme dataclass combining colors with metadata
- CSS generation utilities for Textual theming
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    """Color definitions for a theme.

    All colors should be specified as hex strings (e.g., "#1e1e2e").
    These colors are used to generate Textual CSS for theming.

    Attributes:
        background: Primary background color
        background_secondary: Secondary/alternate background color
        foreground: Primary text color
        foreground_muted: Muted/dimmed text color
        accent: Primary accent color for highlights
        accent_secondary: Secondary accent color
        border: Border color for widgets
        border_focused: Border color when widget is focused
        success: Color for success states (e.g., low CPU usage)
        warning: Color for warning states (e.g., medium CPU usage)
        error: Color for error states (e.g., high CPU usage, errors)
        info: Color for informational elements
        table_header: Table header background color
        table_row_odd: Odd table row background
        table_row_even: Even table row background
        scrollbar: Scrollbar track color
        scrollbar_thumb: Scrollbar thumb color
        progress_bar: Progress bar fill color
        progress_bar_background: Progress bar background color
    """

    # Primary colors
    background: str
    background_secondary: str
    foreground: str
    foreground_muted: str

    # Accent colors
    accent: str
    accent_secondary: str

    # Border colors
    border: str
    border_focused: str

    # Semantic colors
    success: str
    warning: str
    error: str
    info: str

    # Table colors
    table_header: str
    table_row_odd: str
    table_row_even: str

    # Scrollbar colors
    scrollbar: str
    scrollbar_thumb: str

    # Progress bar colors
    progress_bar: str
    progress_bar_background: str


@dataclass(frozen=True)
class Theme:
    """A complete theme definition.

    Combines color definitions with metadata like name and description.

    Attributes:
        name: Unique identifier for the theme
        display_name: Human-readable name for display
        description: Brief description of the theme
        colors: ThemeColors instance with color definitions
        is_dark: Whether this is a dark theme (affects Textual dark mode)
    """

    name: str
    display_name: str
    description: str
    colors: ThemeColors
    is_dark: bool = True


def generate_theme_css(theme: Theme) -> str:
    """Generate Textual CSS from a theme.

    Creates CSS variable definitions and style rules for Textual
    widgets based on the theme colors.

    Args:
        theme: Theme to generate CSS for

    Returns:
        CSS string for the theme
    """
    c = theme.colors

    return f"""
/* uptop theme: {theme.name} */
/* {theme.description} */

/* CSS Variables for theme colors */
$background: {c.background};
$background-secondary: {c.background_secondary};
$foreground: {c.foreground};
$foreground-muted: {c.foreground_muted};
$accent: {c.accent};
$accent-secondary: {c.accent_secondary};
$border: {c.border};
$border-focused: {c.border_focused};
$success: {c.success};
$warning: {c.warning};
$error: {c.error};
$info: {c.info};
$table-header: {c.table_header};
$table-row-odd: {c.table_row_odd};
$table-row-even: {c.table_row_even};
$scrollbar: {c.scrollbar};
$scrollbar-thumb: {c.scrollbar_thumb};
$progress-bar: {c.progress_bar};
$progress-bar-background: {c.progress_bar_background};

/* Base screen styling */
Screen {{
    background: $background;
    color: $foreground;
}}

/* Container styling */
Container {{
    background: $background;
}}

/* Static text */
Static {{
    color: $foreground;
}}

/* Labels */
Label {{
    color: $foreground;
}}

/* Borders and panels */
.panel {{
    border: solid $border;
    background: $background;
}}

.panel:focus {{
    border: solid $border-focused;
}}

/* Headers */
.header {{
    background: $background-secondary;
    color: $foreground;
    text-style: bold;
}}

/* Progress bars */
ProgressBar {{
    background: $progress-bar-background;
}}

ProgressBar > .bar--bar {{
    color: $progress-bar;
}}

ProgressBar > .bar--complete {{
    color: $success;
}}

/* Bar widget for gauges */
Bar {{
    background: $progress-bar-background;
    color: $progress-bar;
}}

/* Data tables */
DataTable {{
    background: $background;
}}

DataTable > .datatable--header {{
    background: $table-header;
    color: $foreground;
    text-style: bold;
}}

DataTable > .datatable--cursor {{
    background: $accent;
    color: $background;
}}

DataTable > .datatable--odd-row {{
    background: $table-row-odd;
}}

DataTable > .datatable--even-row {{
    background: $table-row-even;
}}

/* Scrollbars */
ScrollBar {{
    background: $scrollbar;
}}

ScrollBar > .scrollbar--thumb {{
    background: $scrollbar-thumb;
}}

/* Button styling */
Button {{
    background: $accent;
    color: $background;
    border: none;
}}

Button:hover {{
    background: $accent-secondary;
}}

Button:focus {{
    border: solid $border-focused;
}}

/* Input styling */
Input {{
    background: $background-secondary;
    color: $foreground;
    border: solid $border;
}}

Input:focus {{
    border: solid $border-focused;
}}

/* Footer/status bar */
Footer {{
    background: $background-secondary;
    color: $foreground-muted;
}}

/* Tabs */
Tabs {{
    background: $background;
}}

Tab {{
    background: $background-secondary;
    color: $foreground-muted;
}}

Tab.-active {{
    background: $accent;
    color: $background;
}}

/* Rule/separator */
Rule {{
    color: $border;
}}

/* Semantic status classes */
.status-success {{
    color: $success;
}}

.status-warning {{
    color: $warning;
}}

.status-error {{
    color: $error;
}}

.status-info {{
    color: $info;
}}

/* Muted/secondary text */
.muted {{
    color: $foreground-muted;
}}

/* Accent text */
.accent {{
    color: $accent;
}}

/* Enhanced focus indicators for accessibility */
*:focus {{
    border: double $border-focused;
}}

/* Visual feedback for keyboard navigation on panes */
.pane-focused {{
    border: double $accent;
}}

/* Section separators for visual clarity */
.section-separator {{
    border-bottom: solid $border;
    margin-bottom: 1;
    padding-bottom: 1;
}}

/* Loading state styling */
.loading-state {{
    opacity: 0.7;
}}

/* Stale data indicator */
.stale-state {{
    border: dashed $warning;
}}

/* Error state styling */
.error-state {{
    border: solid $error;
}}

/* Data update highlight effect */
.data-updated {{
    background: $accent 10%;
}}

/* LoadingIndicator styling */
LoadingIndicator {{
    color: $accent;
}}
"""
