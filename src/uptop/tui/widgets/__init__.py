"""Widget components for uptop TUI.

This module provides reusable widget components:
- PaneContainer: A bordered container widget for panes with title bar,
  refresh indicator, and error state display.
- Sparkline: A compact horizontal bar graph showing historical values.
"""

from uptop.tui.widgets.pane_container import PaneContainer, PaneState
from uptop.tui.widgets.sparkline import Sparkline

__all__ = [
    "PaneContainer",
    "PaneState",
    "Sparkline",
]
