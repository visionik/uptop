"""TUI screens module for uptop.

This module provides:
- HelpScreen: Modal overlay showing keybindings and help
- FilterScreen: Modal overlay for filtering processes
- ConfirmKillScreen: Modal overlay for confirming process termination
- LoadingScreen: Loading screen shown during startup
- CommandPaletteScreen: Modal overlay for switching plugins and layouts
- KillResult: Result dataclass from kill confirmation
- KillSignal: Enum for kill signal selection
- CommandPaletteResult: Result dataclass from command palette
"""

from uptop.tui.screens.command_palette import CommandPaletteResult, CommandPaletteScreen
from uptop.tui.screens.confirm_kill import ConfirmKillScreen, KillResult, KillSignal
from uptop.tui.screens.filter import FilterScreen
from uptop.tui.screens.help import HelpScreen
from uptop.tui.screens.loading import LoadingScreen

__all__ = [
    "CommandPaletteResult",
    "CommandPaletteScreen",
    "ConfirmKillScreen",
    "FilterScreen",
    "HelpScreen",
    "LoadingScreen",
    "KillResult",
    "KillSignal",
]
