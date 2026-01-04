"""Dark theme for uptop TUI.

This is the default theme with a dark background and light text.
Color scheme inspired by Catppuccin Mocha.
"""

from uptop.tui.themes.base import Theme, ThemeColors

DARK_COLORS = ThemeColors(
    # Primary colors
    background="#1e1e2e",
    background_secondary="#313244",
    foreground="#cdd6f4",
    foreground_muted="#6c7086",
    # Accent colors
    accent="#89b4fa",
    accent_secondary="#74c7ec",
    # Border colors
    border="#45475a",
    border_focused="#89b4fa",
    # Semantic colors
    success="#a6e3a1",
    warning="#f9e2af",
    error="#f38ba8",
    info="#89dceb",
    # Table colors
    table_header="#313244",
    table_row_odd="#1e1e2e",
    table_row_even="#262637",
    # Scrollbar colors
    scrollbar="#313244",
    scrollbar_thumb="#585b70",
    # Progress bar colors
    progress_bar="#89b4fa",
    progress_bar_background="#313244",
)

DARK_THEME = Theme(
    name="dark",
    display_name="Dark",
    description="Default dark theme with comfortable contrast",
    colors=DARK_COLORS,
    is_dark=True,
)
