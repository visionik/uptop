"""Nord theme for uptop TUI.

An arctic, north-bluish color palette.
Inspired by the beauty of the arctic.
"""

from uptop.tui.themes.base import Theme, ThemeColors

NORD_COLORS = ThemeColors(
    # Primary colors (Nord Polar Night)
    background="#2e3440",
    background_secondary="#3b4252",
    foreground="#eceff4",
    foreground_muted="#d8dee9",
    # Accent colors (Nord Frost)
    accent="#88c0d0",
    accent_secondary="#81a1c1",
    # Border colors
    border="#4c566a",
    border_focused="#88c0d0",
    # Semantic colors (Nord Aurora)
    success="#a3be8c",
    warning="#ebcb8b",
    error="#bf616a",
    info="#5e81ac",
    # Table colors
    table_header="#3b4252",
    table_row_odd="#2e3440",
    table_row_even="#343a47",
    # Scrollbar colors
    scrollbar="#3b4252",
    scrollbar_thumb="#4c566a",
    # Progress bar colors
    progress_bar="#88c0d0",
    progress_bar_background="#3b4252",
)

NORD_THEME = Theme(
    name="nord",
    display_name="Nord",
    description="Arctic, north-bluish color palette",
    colors=NORD_COLORS,
    is_dark=True,
)
