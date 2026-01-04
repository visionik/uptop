"""Gruvbox dark theme for uptop TUI.

Retro groove color scheme with warm colors.
Designed for reduced eye strain during long coding sessions.
"""

from uptop.tui.themes.base import Theme, ThemeColors

GRUVBOX_COLORS = ThemeColors(
    # Primary colors
    background="#282828",
    background_secondary="#3c3836",
    foreground="#ebdbb2",
    foreground_muted="#a89984",
    # Accent colors
    accent="#fabd2f",
    accent_secondary="#fe8019",
    # Border colors
    border="#504945",
    border_focused="#fabd2f",
    # Semantic colors
    success="#b8bb26",
    warning="#fabd2f",
    error="#fb4934",
    info="#83a598",
    # Table colors
    table_header="#3c3836",
    table_row_odd="#282828",
    table_row_even="#32302f",
    # Scrollbar colors
    scrollbar="#3c3836",
    scrollbar_thumb="#504945",
    # Progress bar colors
    progress_bar="#fabd2f",
    progress_bar_background="#3c3836",
)

GRUVBOX_THEME = Theme(
    name="gruvbox",
    display_name="Gruvbox",
    description="Retro groove color scheme with warm colors",
    colors=GRUVBOX_COLORS,
    is_dark=True,
)
