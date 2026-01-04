"""Light theme for uptop TUI.

A light theme with good contrast for readability.
Color scheme inspired by Catppuccin Latte.
"""

from uptop.tui.themes.base import Theme, ThemeColors

LIGHT_COLORS = ThemeColors(
    # Primary colors
    background="#eff1f5",
    background_secondary="#dce0e8",
    foreground="#4c4f69",
    foreground_muted="#8c8fa1",
    # Accent colors
    accent="#1e66f5",
    accent_secondary="#7287fd",
    # Border colors
    border="#bcc0cc",
    border_focused="#1e66f5",
    # Semantic colors
    success="#40a02b",
    warning="#df8e1d",
    error="#d20f39",
    info="#04a5e5",
    # Table colors
    table_header="#dce0e8",
    table_row_odd="#eff1f5",
    table_row_even="#e6e9ef",
    # Scrollbar colors
    scrollbar="#dce0e8",
    scrollbar_thumb="#9ca0b0",
    # Progress bar colors
    progress_bar="#1e66f5",
    progress_bar_background="#dce0e8",
)

LIGHT_THEME = Theme(
    name="light",
    display_name="Light",
    description="Light theme with high contrast for bright environments",
    colors=LIGHT_COLORS,
    is_dark=False,
)
