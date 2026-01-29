"""Layout components for uptop TUI.

This module provides layout management for arranging panes:
- GridLayout: A flexible grid-based layout for pane arrangement
- Default layout configurations for standard pane layouts
- Template system for declarative layout definitions
"""

from uptop.tui.layouts.grid import (
    DEFAULT_LAYOUT_CONFIG,
    GridLayout,
    LayoutConfig,
    PanePosition,
)
from uptop.tui.layouts.templates import (
    COMPACT_LAYOUT,
    DASHBOARD,
    DETAILED_LAYOUT,
    PROCESSES_FOCUSED,
    SPLIT_SCREEN,
    STANDARD_LAYOUT,
    LayoutTemplate,
    LayoutTemplates,
    PaneHeight,
    PaneSpec,
    PaneWidth,
    RowSpec,
)

__all__ = [
    # Grid components
    "GridLayout",
    "LayoutConfig",
    "PanePosition",
    "DEFAULT_LAYOUT_CONFIG",
    # Template system
    "LayoutTemplate",
    "LayoutTemplates",
    "PaneSpec",
    "RowSpec",
    "PaneWidth",
    "PaneHeight",
    # Predefined templates
    "STANDARD_LAYOUT",
    "COMPACT_LAYOUT",
    "DETAILED_LAYOUT",
    "PROCESSES_FOCUSED",
    "SPLIT_SCREEN",
    "DASHBOARD",
]
