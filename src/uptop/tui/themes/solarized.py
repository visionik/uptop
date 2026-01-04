"""Solarized dark theme for uptop TUI.

The classic Solarized color scheme by Ethan Schoonover.
Designed for optimal readability with low eye strain.
"""

from uptop.tui.themes.base import Theme, ThemeColors

SOLARIZED_COLORS = ThemeColors(
    # Primary colors
    background="#002b36",
    background_secondary="#073642",
    foreground="#839496",
    foreground_muted="#586e75",
    # Accent colors
    accent="#268bd2",
    accent_secondary="#2aa198",
    # Border colors
    border="#586e75",
    border_focused="#268bd2",
    # Semantic colors
    success="#859900",
    warning="#b58900",
    error="#dc322f",
    info="#2aa198",
    # Table colors
    table_header="#073642",
    table_row_odd="#002b36",
    table_row_even="#003847",
    # Scrollbar colors
    scrollbar="#073642",
    scrollbar_thumb="#586e75",
    # Progress bar colors
    progress_bar="#268bd2",
    progress_bar_background="#073642",
)

SOLARIZED_THEME = Theme(
    name="solarized",
    display_name="Solarized Dark",
    description="Classic Solarized dark theme for low eye strain",
    colors=SOLARIZED_COLORS,
    is_dark=True,
)
