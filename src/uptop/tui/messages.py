"""Custom Textual messages for uptop TUI.

This module defines custom messages for inter-widget communication:
- DisplayModeChanged: Posted when a pane's display mode is cycled
- PaneResized: Posted when a pane is resized
"""

from textual.message import Message


class DisplayModeChanged(Message):
    """Posted when a pane's display mode changes.

    This message is posted by PaneContainer when the user cycles
    the display mode with the 'm' key. The app handles this message
    by refreshing the affected pane.

    Attributes:
        pane_name: Name of the pane whose mode changed (e.g., "cpu", "memory")
    """

    def __init__(self, pane_name: str) -> None:
        """Initialize the message.

        Args:
            pane_name: Name of the pane whose mode changed
        """
        self.pane_name = pane_name
        super().__init__()


class PaneResized(Message):
    """Posted when a pane is resized.

    This message is posted by PaneContainer when its size changes,
    allowing the app to re-render the pane with the new dimensions.

    Attributes:
        pane_name: Name of the pane that was resized
        width: New width in terminal cells
        height: New height in terminal cells
    """

    def __init__(self, pane_name: str, width: int, height: int) -> None:
        """Initialize the message.

        Args:
            pane_name: Name of the pane that was resized
            width: New width in cells
            height: New height in cells
        """
        self.pane_name = pane_name
        self.width = width
        self.height = height
        super().__init__()


class PluginSwapped(Message):
    """Posted when a plugin is swapped in a pane slot.

    This message is posted by GridLayout when swap_plugin() is called,
    allowing the app to reload the pane with the new plugin.

    Attributes:
        pane_name: Name of the pane slot
        old_plugin: Previous plugin name
        new_plugin: New plugin name
    """

    def __init__(self, pane_name: str, old_plugin: str, new_plugin: str) -> None:
        """Initialize the message.

        Args:
            pane_name: Name of the pane slot
            old_plugin: Previous plugin name
            new_plugin: New plugin name
        """
        self.pane_name = pane_name
        self.old_plugin = old_plugin
        self.new_plugin = new_plugin
        super().__init__()


class LayoutSwitchRequested(Message):
    """Posted when a layout switch is requested.

    This message is posted by GridLayout when a layout preset keybinding
    is pressed (Alt+1-6), allowing the app to switch the entire layout.

    Attributes:
        layout_name: Name of the requested layout preset
    """

    def __init__(self, layout_name: str) -> None:
        """Initialize the message.

        Args:
            layout_name: Name of the requested layout preset
        """
        self.layout_name = layout_name
        super().__init__()
