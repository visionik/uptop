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
