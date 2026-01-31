"""Command Palette screen for uptop.

This module provides:
- CommandPaletteScreen: A modal overlay for switching plugins and layouts
- Fuzzy search through available plugins and layout presets
- Quick keyboard-driven workflow (Ctrl+P to open)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListView, ListItem, Static

if TYPE_CHECKING:
    from uptop.plugins.registry import PluginRegistry
    from uptop.tui.layouts.templates import LayoutTemplate


@dataclass
class CommandPaletteResult:
    """Result from the command palette.

    Attributes:
        action_type: Type of action - "plugin" or "layout"
        target: For plugin: plugin_name, for layout: layout_name
        pane_slot: For plugin switching, which pane slot to target (None = focused)
    """

    action_type: str  # "plugin" | "layout"
    target: str
    pane_slot: str | None = None


class CommandItem(ListItem):
    """A single selectable item in the command palette.

    Displays the item name, description, and type badge.
    """

    DEFAULT_CSS = """
    CommandItem {
        height: auto;
        padding: 0 1;
    }

    CommandItem .item-header {
        width: 100%;
        height: auto;
    }

    CommandItem .item-name {
        text-style: bold;
        color: $accent;
    }

    CommandItem .item-badge {
        color: $warning;
        text-style: italic;
    }

    CommandItem .item-description {
        color: $text-muted;
        margin-left: 2;
    }

    CommandItem:hover {
        background: $accent 20%;
    }
    """

    def __init__(
        self,
        name: str,
        description: str,
        badge: str,
        action_type: str,
        target: str,
        *,
        id: str | None = None,  # noqa: A002
    ) -> None:
        """Initialize a command item.

        Args:
            name: Display name of the item
            description: Brief description
            badge: Type badge (e.g., "PLUGIN", "LAYOUT")
            action_type: Action type ("plugin" or "layout")
            target: Target identifier (plugin name or layout name)
            id: Widget ID
        """
        super().__init__(id=id)
        self._name = name
        self._description = description
        self._badge = badge
        self._action_type = action_type
        self._target = target

    def compose(self) -> ComposeResult:
        """Compose the command item."""
        with Vertical(classes="item-header"):
            header = f"[bold]{self._name}[/bold]  [italic yellow]{self._badge}[/italic yellow]"
            yield Static(header)
            if self._description:
                yield Static(f"  {self._description}", classes="item-description")

    @property
    def action_type(self) -> str:
        """Get the action type."""
        return self._action_type

    @property
    def target(self) -> str:
        """Get the target identifier."""
        return self._target


class CommandPaletteScreen(ModalScreen[CommandPaletteResult | None]):
    """Modal screen for switching plugins and layouts via command palette.

    Features:
    - Fuzzy search through available plugins and layouts
    - Keyboard-driven navigation (arrows + Enter)
    - Shows plugin/layout descriptions
    - ESC to dismiss

    Attributes:
        BINDINGS: Key bindings for navigation and dismissal
    """

    BINDINGS = [
        Binding("escape", "dismiss_palette", "Close", show=True),
        Binding("ctrl+c", "dismiss_palette", "Close", show=False),
        Binding("enter", "select_item", "Select", show=True),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
    ]

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center top;
        padding-top: 3;
    }

    CommandPaletteScreen > Container {
        width: 80;
        max-width: 100;
        height: auto;
        max-height: 80%;
        background: $background;
        border: solid $accent;
        padding: 0;
    }

    CommandPaletteScreen .palette-title {
        dock: top;
        width: 100%;
        height: 3;
        background: $accent;
        color: $background;
        text-align: center;
        padding: 1 0;
        text-style: bold;
    }

    CommandPaletteScreen .search-container {
        dock: top;
        width: 100%;
        height: auto;
        padding: 1 2;
        background: $surface;
    }

    CommandPaletteScreen Input {
        width: 100%;
        border: solid $primary;
    }

    CommandPaletteScreen Input:focus {
        border: solid $accent;
    }

    CommandPaletteScreen .results-container {
        width: 100%;
        height: 1fr;
        padding: 0;
    }

    CommandPaletteScreen ListView {
        width: 100%;
        height: 100%;
        padding: 1 0;
    }

    CommandPaletteScreen .no-results {
        width: 100%;
        height: 5;
        content-align: center middle;
        color: $text-muted;
    }

    CommandPaletteScreen .footer-hint {
        dock: bottom;
        width: 100%;
        height: 2;
        text-align: center;
        color: $text-muted;
        padding: 0 2;
        border-top: solid $border;
    }
    """

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        layout_templates: dict[str, LayoutTemplate],
        focused_pane: str | None = None,
    ) -> None:
        """Initialize the command palette.

        Args:
            plugin_registry: Registry of available plugins
            layout_templates: Dictionary of available layout templates
            focused_pane: Currently focused pane name (for targeted plugin switching)
        """
        super().__init__()
        self._plugin_registry = plugin_registry
        self._layout_templates = layout_templates
        self._focused_pane = focused_pane
        self._all_items: list[CommandItem] = []
        self._filtered_items: list[CommandItem] = []

    def compose(self) -> ComposeResult:
        """Compose the command palette layout."""
        with Container():
            yield Label("Command Palette", classes="palette-title")

            with Vertical(classes="search-container"):
                yield Input(placeholder="Search plugins and layouts...", id="search-input")

            with Vertical(classes="results-container", id="results-area"):
                yield ListView(id="results-list")

            yield Label(
                "↑↓ Navigate  •  Enter Select  •  Esc Close",
                classes="footer-hint",
            )

    def on_mount(self) -> None:
        """Handle mount event - build item list and focus search."""
        self._build_item_list()
        self._update_results("")

        # Focus the search input
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def _build_item_list(self) -> None:
        """Build the list of all available commands (plugins + layouts)."""
        items = []

        # Add layout templates
        for name, template in self._layout_templates.items():
            items.append(
                CommandItem(
                    name=template.name.title(),
                    description=template.description,
                    badge="LAYOUT",
                    action_type="layout",
                    target=name,
                    id=f"cmd-layout-{name}",
                )
            )

        # Add plugins from registry
        try:
            from uptop.models.base import PluginType
            import logging
            logger = logging.getLogger(__name__)
            
            pane_plugins = self._plugin_registry.get_plugins_by_type(PluginType.PANE)
            logger.info(f"Found {len(pane_plugins)} pane plugins")
            
            for plugin in pane_plugins:
                metadata = plugin.get_metadata()
                logger.info(f"Adding plugin to palette: {metadata.name} - {metadata.display_name}")
                items.append(
                    CommandItem(
                        name=metadata.display_name,
                        description=metadata.description or "",
                        badge="PLUGIN",
                        action_type="plugin",
                        target=metadata.name,
                        id=f"cmd-plugin-{metadata.name}",
                    )
                )
        except Exception as e:
            # Registry might not have plugins yet, skip
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load plugins into command palette: {e}", exc_info=True)
            pass

        self._all_items = items
        self._filtered_items = items.copy()

    def _update_results(self, query: str) -> None:
        """Update the results list based on search query.

        Args:
            query: Search query string
        """
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()

        # Simple fuzzy matching - case insensitive, all query chars must appear in order
        query_lower = query.lower()

        if not query_lower:
            # Show all items when query is empty
            self._filtered_items = self._all_items.copy()
        else:
            # Filter by fuzzy match
            filtered = []
            for item in self._all_items:
                # Match against name and description
                search_text = f"{item._name} {item._description}".lower()

                # Check if all characters in query appear in order
                query_idx = 0
                for char in search_text:
                    if query_idx < len(query_lower) and char == query_lower[query_idx]:
                        query_idx += 1

                if query_idx == len(query_lower):
                    filtered.append(item)

            self._filtered_items = filtered

        # Populate list
        if self._filtered_items:
            for item in self._filtered_items:
                results_list.append(item)

            # Auto-select first item
            if results_list.children:
                results_list.index = 0
        else:
            # Show "no results" message
            results_area = self.query_one("#results-area", Vertical)
            if results_area.query(".no-results"):
                return  # Already showing
            # Remove ListView and show message
            results_list.remove()
            results_area.mount(Static("No matching plugins or layouts found.", classes="no-results"))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes.

        Args:
            event: Input changed event
        """
        self._update_results(event.value)

    def action_cursor_up(self) -> None:
        """Move selection up in the list."""
        try:
            results_list = self.query_one("#results-list", ListView)
            if results_list.index is not None and results_list.index > 0:
                results_list.index -= 1
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        """Move selection down in the list."""
        try:
            results_list = self.query_one("#results-list", ListView)
            if results_list.index is not None:
                results_list.index = min(results_list.index + 1, len(results_list.children) - 1)
        except Exception:
            pass

    def action_select_item(self) -> None:
        """Select the currently highlighted item."""
        try:
            results_list = self.query_one("#results-list", ListView)
            if results_list.highlighted_child:
                item = results_list.highlighted_child
                if isinstance(item, CommandItem):
                    result = CommandPaletteResult(
                        action_type=item.action_type,
                        target=item.target,
                        pane_slot=self._focused_pane,
                    )
                    self.dismiss(result)
        except Exception:
            self.dismiss(None)

    def action_dismiss_palette(self) -> None:
        """Dismiss the palette without selecting."""
        self.dismiss(None)
