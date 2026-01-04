"""Grid Layout for uptop TUI.

This module provides:
- GridLayout: A flexible grid-based layout widget for arranging panes
- LayoutConfig: Configuration for layout structure
- PanePosition: Position information for a pane in the grid
- Focus cycling support (Tab/Shift+Tab navigation)

The default layout arranges panes as:
- Top row: CPU (left, 50%), Memory (right, 50%)
- Middle row: Processes (full width, larger height)
- Bottom row: Network (left, 50%), Disk (right, 50%)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from uptop.tui.widgets.pane_container import PaneContainer

if TYPE_CHECKING:
    from uptop.config import Config


@dataclass
class PanePosition:
    """Position and size information for a pane in the grid.

    Attributes:
        name: Unique identifier for the pane (e.g., "cpu", "memory")
        row: Row index (0-based)
        col: Column index (0-based) within the row
        row_span: Number of rows the pane spans (default 1)
        col_span: Fraction of the row width (1.0 = full width, 0.5 = half)
        height_weight: Relative height weight for the row (default 1)
    """

    name: str
    row: int
    col: int
    row_span: int = 1
    col_span: float = 0.5
    height_weight: int = 1


@dataclass
class LayoutConfig:
    """Configuration for the grid layout.

    Attributes:
        name: Name of this layout configuration
        panes: List of pane positions defining the layout
        row_heights: Optional list of relative row heights (fr units)
    """

    name: str
    panes: list[PanePosition] = field(default_factory=list)
    row_heights: list[int] = field(default_factory=list)

    def get_pane_names(self) -> list[str]:
        """Get ordered list of pane names for focus cycling.

        Returns:
            List of pane names in focus order (row by row, left to right)
        """
        # Sort by row, then by column
        sorted_panes = sorted(self.panes, key=lambda p: (p.row, p.col))
        return [p.name for p in sorted_panes]

    def get_rows(self) -> list[list[PanePosition]]:
        """Group panes by row.

        Returns:
            List of rows, each containing list of pane positions
        """
        if not self.panes:
            return []

        max_row = max(p.row for p in self.panes)
        rows: list[list[PanePosition]] = [[] for _ in range(max_row + 1)]

        for pane in self.panes:
            rows[pane.row].append(pane)

        # Sort each row by column
        for row in rows:
            row.sort(key=lambda p: p.col)

        return rows


# Default layout: CPU+Memory top, Processes middle (full width), Network+Disk bottom
DEFAULT_LAYOUT_CONFIG = LayoutConfig(
    name="standard",
    panes=[
        PanePosition(name="cpu", row=0, col=0, col_span=0.5, height_weight=1),
        PanePosition(name="memory", row=0, col=1, col_span=0.5, height_weight=1),
        PanePosition(name="processes", row=1, col=0, col_span=1.0, height_weight=2),
        PanePosition(name="network", row=2, col=0, col_span=0.5, height_weight=1),
        PanePosition(name="disk", row=2, col=1, col_span=0.5, height_weight=1),
    ],
    row_heights=[1, 2, 1],  # Processes row is twice as tall
)


class PlaceholderContent(Static):
    """Placeholder content for panes during development.

    This will be replaced with actual pane widgets in Phase 3.4.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    PlaceholderContent {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def __init__(self, pane_name: str) -> None:
        """Initialize placeholder with pane name.

        Args:
            pane_name: Name of the pane this placeholder is for
        """
        super().__init__()
        self._pane_name = pane_name

    def render(self) -> str:
        """Render placeholder text."""
        return f"[{self._pane_name}]\n\nPane content will appear here..."


class GridRow(Horizontal):
    """A horizontal row in the grid layout.

    Contains one or more PaneContainers arranged horizontally.
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    GridRow {
        width: 100%;
        height: auto;
    }
    """


class GridLayout(Container):
    """Grid-based layout widget for arranging panes.

    The GridLayout manages the arrangement of panes in a grid structure,
    with support for:
    - Configurable row and column layout
    - Pane visibility toggling
    - Focus cycling between panes (Tab/Shift+Tab)
    - Row height weighting

    The layout is composed of rows, each containing one or more pane containers.
    Panes can span different portions of a row (e.g., half width, full width).

    Attributes:
        layout_config: The LayoutConfig defining the grid structure
        config: Optional application configuration for pane settings

    Example:
        ```python
        class MyApp(App):
            def compose(self) -> ComposeResult:
                yield GridLayout(config=self.config)
        ```
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    GridLayout {
        width: 100%;
        height: 100%;
        layout: vertical;
        padding: 0;
    }

    GridLayout > Vertical {
        width: 100%;
        height: 100%;
        padding: 0;
    }

    GridLayout GridRow {
        width: 100%;
        padding: 0;
    }

    /* Row height weights - applied dynamically */
    GridLayout .row-weight-1 {
        height: 1fr;
    }

    GridLayout .row-weight-2 {
        height: 2fr;
    }

    GridLayout .row-weight-3 {
        height: 3fr;
    }

    /* Pane width classes */
    GridLayout .pane-half {
        width: 1fr;
    }

    GridLayout .pane-full {
        width: 100%;
    }

    GridLayout .pane-third {
        width: 1fr;
    }

    GridLayout PaneContainer {
        height: 100%;
        margin: 0;
    }

    /* Consistent spacing between panes */
    GridLayout GridRow > PaneContainer {
        margin-right: 0;
    }

    GridLayout GridRow > PaneContainer:last-child {
        margin-right: 0;
    }
    """

    BINDINGS = [
        Binding("tab", "focus_next_pane", "Next Pane", show=True),
        Binding("shift+tab", "focus_previous_pane", "Previous Pane", show=True),
        Binding("1", "focus_pane_1", "Focus Pane 1", show=False),
        Binding("2", "focus_pane_2", "Focus Pane 2", show=False),
        Binding("3", "focus_pane_3", "Focus Pane 3", show=False),
        Binding("4", "focus_pane_4", "Focus Pane 4", show=False),
        Binding("5", "focus_pane_5", "Focus Pane 5", show=False),
    ]

    def __init__(
        self,
        layout_config: LayoutConfig | None = None,
        config: Config | None = None,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the grid layout.

        Args:
            layout_config: Layout configuration defining grid structure.
                          Defaults to DEFAULT_LAYOUT_CONFIG if not provided.
            config: Optional application configuration for pane settings
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._layout_config = layout_config or DEFAULT_LAYOUT_CONFIG
        self._config = config
        self._focus_order: list[str] = []
        self._current_focus_index: int = 0
        self._hidden_panes: set[str] = set()
        self._pane_widgets: dict[str, PaneContainer] = {}

    @property
    def layout_config(self) -> LayoutConfig:
        """Get the current layout configuration."""
        return self._layout_config

    @property
    def focus_order(self) -> list[str]:
        """Get the pane focus order (read-only copy)."""
        return self._focus_order.copy()

    @property
    def visible_panes(self) -> list[str]:
        """Get list of currently visible pane names."""
        return [name for name in self._focus_order if name not in self._hidden_panes]

    def compose(self) -> ComposeResult:
        """Compose the grid layout with rows and pane containers.

        Yields:
            Vertical container with rows of pane containers
        """
        # Build focus order from layout config
        self._focus_order = self._layout_config.get_pane_names()

        # Get rows from layout config
        rows = self._layout_config.get_rows()
        row_heights = self._layout_config.row_heights

        with Vertical():
            for row_idx, row_panes in enumerate(rows):
                # Determine row height weight
                height_weight = 1
                if row_idx < len(row_heights):
                    height_weight = row_heights[row_idx]
                elif row_panes:
                    # Use the first pane's height_weight if no explicit row height
                    height_weight = row_panes[0].height_weight

                # Create row container with height weight class
                weight_class = f"row-weight-{min(height_weight, 3)}"
                row_id = f"grid-row-{row_idx}"

                with GridRow(id=row_id, classes=weight_class):
                    for pane_pos in row_panes:
                        yield self._create_pane_container(pane_pos)

    def _create_pane_container(self, pane_pos: PanePosition) -> PaneContainer:
        """Create a PaneContainer for the given position.

        Args:
            pane_pos: Position configuration for the pane

        Returns:
            Configured PaneContainer widget
        """
        # Determine width class based on col_span
        if pane_pos.col_span >= 1.0:
            width_class = "pane-full"
        elif pane_pos.col_span >= 0.5:
            width_class = "pane-half"
        else:
            width_class = "pane-third"

        # Get pane-specific config if available
        refresh_interval = 1.0
        if self._config:
            pane_config = self._config.get_pane_config(pane_pos.name)
            refresh_interval = pane_config.refresh_interval

        # Create display title (capitalize first letter)
        display_title = pane_pos.name.replace("_", " ").title()

        # Create the pane container with placeholder content
        pane = PaneContainer(
            title=display_title,
            refresh_interval=refresh_interval,
            content=PlaceholderContent(pane_pos.name),
            id=f"pane-{pane_pos.name}",
            classes=width_class,
        )

        # Store reference for later access
        self._pane_widgets[pane_pos.name] = pane

        return pane

    def on_mount(self) -> None:
        """Handle mount event - set initial focus."""
        # Focus the first visible pane if any exist
        if self.visible_panes:
            self._focus_pane_by_name(self.visible_panes[0])

    def get_pane(self, name: str) -> PaneContainer | None:
        """Get a pane container by name.

        Args:
            name: The pane name (e.g., "cpu", "memory")

        Returns:
            The PaneContainer if found, None otherwise
        """
        return self._pane_widgets.get(name)

    def get_focused_pane(self) -> PaneContainer | None:
        """Get the currently focused pane container.

        Returns:
            The focused PaneContainer if any, None otherwise
        """
        visible = self.visible_panes
        if not visible or self._current_focus_index >= len(visible):
            return None
        return self._pane_widgets.get(visible[self._current_focus_index])

    def _focus_pane_by_name(self, name: str) -> bool:
        """Focus a specific pane by name.

        Args:
            name: The pane name to focus

        Returns:
            True if pane was found and focused, False otherwise
        """
        visible = self.visible_panes
        if name not in visible:
            return False

        self._current_focus_index = visible.index(name)
        pane = self._pane_widgets.get(name)
        if pane:
            pane.focus()
            return True
        return False

    def _focus_pane_by_index(self, index: int) -> bool:
        """Focus a pane by its index in the visible panes list.

        Args:
            index: Index in the visible panes list

        Returns:
            True if pane was focused, False otherwise
        """
        visible = self.visible_panes
        if not visible:
            return False

        # Wrap index around
        index = index % len(visible)
        self._current_focus_index = index

        pane_name = visible[index]
        pane = self._pane_widgets.get(pane_name)
        if pane:
            pane.focus()
            return True
        return False

    def action_focus_next_pane(self) -> None:
        """Focus the next pane in the cycle order (Tab)."""
        visible = self.visible_panes
        if not visible:
            return

        next_index = (self._current_focus_index + 1) % len(visible)
        self._focus_pane_by_index(next_index)

    def action_focus_previous_pane(self) -> None:
        """Focus the previous pane in the cycle order (Shift+Tab)."""
        visible = self.visible_panes
        if not visible:
            return

        prev_index = (self._current_focus_index - 1) % len(visible)
        self._focus_pane_by_index(prev_index)

    def action_focus_pane_1(self) -> None:
        """Focus the first pane (number key 1)."""
        self._focus_pane_by_index(0)

    def action_focus_pane_2(self) -> None:
        """Focus the second pane (number key 2)."""
        self._focus_pane_by_index(1)

    def action_focus_pane_3(self) -> None:
        """Focus the third pane (number key 3)."""
        self._focus_pane_by_index(2)

    def action_focus_pane_4(self) -> None:
        """Focus the fourth pane (number key 4)."""
        self._focus_pane_by_index(3)

    def action_focus_pane_5(self) -> None:
        """Focus the fifth pane (number key 5)."""
        self._focus_pane_by_index(4)

    def show_pane(self, name: str) -> bool:
        """Show a hidden pane.

        Args:
            name: The pane name to show

        Returns:
            True if pane was shown, False if not found or already visible
        """
        if name not in self._hidden_panes:
            return False

        self._hidden_panes.discard(name)

        # Update pane visibility
        pane = self._pane_widgets.get(name)
        if pane:
            pane.display = True
            return True
        return False

    def hide_pane(self, name: str) -> bool:
        """Hide a visible pane.

        Args:
            name: The pane name to hide

        Returns:
            True if pane was hidden, False if not found or already hidden
        """
        if name in self._hidden_panes:
            return False

        if name not in self._focus_order:
            return False

        self._hidden_panes.add(name)

        # Update pane visibility
        pane = self._pane_widgets.get(name)
        if pane:
            pane.display = False

            # If this was the focused pane, move focus
            visible = self.visible_panes
            if visible:
                # Try to maintain similar position in the list
                new_index = min(self._current_focus_index, len(visible) - 1)
                self._focus_pane_by_index(new_index)

            return True
        return False

    def toggle_pane(self, name: str) -> bool:
        """Toggle a pane's visibility.

        Args:
            name: The pane name to toggle

        Returns:
            True if pane is now visible, False if now hidden
        """
        if name in self._hidden_panes:
            self.show_pane(name)
            return True
        self.hide_pane(name)
        return False

    def is_pane_visible(self, name: str) -> bool:
        """Check if a pane is currently visible.

        Args:
            name: The pane name to check

        Returns:
            True if pane exists and is visible, False otherwise
        """
        return name in self._focus_order and name not in self._hidden_panes

    def set_layout(self, layout_config: LayoutConfig) -> None:
        """Change the layout configuration.

        Note: This will trigger a recompose of the widget.

        Args:
            layout_config: New layout configuration to apply
        """
        self._layout_config = layout_config
        self._hidden_panes.clear()
        self._pane_widgets.clear()
        self._current_focus_index = 0
        self.refresh(recompose=True)

    def get_visible_pane_widgets(self) -> Sequence[PaneContainer]:
        """Get all visible pane container widgets.

        Returns:
            Sequence of visible PaneContainer widgets in focus order
        """
        return [
            self._pane_widgets[name] for name in self.visible_panes if name in self._pane_widgets
        ]
