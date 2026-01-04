"""Sparkline Widget for uptop TUI.

This module provides a sparkline widget for displaying historical values
as a compact horizontal bar graph using Unicode block characters.

The sparkline uses 9 levels of block characters to represent values:
" ▁▂▃▄▅▆▇█" (space for 0, full block for maximum)

Color coding is based on the most recent value:
- Green: 0-50% (low usage)
- Yellow: 50-80% (medium usage)
- Red: 80-100% (high usage)
"""

from collections import deque
from typing import ClassVar

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

# Unicode block characters for sparkline (9 levels: 0-8)
SPARK_CHARS = " ▁▂▃▄▅▆▇█"

# Color thresholds for usage display
THRESHOLD_LOW = 50.0  # 0-50% is green (low usage)
THRESHOLD_MEDIUM = 80.0  # 50-80% is yellow (medium usage)
# Above 80% is red (high usage)


def value_to_char(value: float, min_val: float = 0.0, max_val: float = 100.0) -> str:
    """Convert a value to a sparkline character.

    Args:
        value: The value to convert
        min_val: Minimum value in the range
        max_val: Maximum value in the range

    Returns:
        A Unicode block character representing the value
    """
    if max_val == min_val:
        # Avoid division by zero; if range is zero, return middle char
        return SPARK_CHARS[4]

    # Clamp value to range
    value = max(min_val, min(max_val, value))

    # Normalize to 0-1 range
    normalized = (value - min_val) / (max_val - min_val)

    # Map to character index (0-8)
    index = int(normalized * 8)
    index = max(0, min(8, index))

    return SPARK_CHARS[index]


def get_value_color(value: float) -> str:
    """Get the color name for a given value (as percentage 0-100).

    Args:
        value: Value as a percentage (0-100)

    Returns:
        Color name: 'green', 'yellow', or 'red'
    """
    if value < THRESHOLD_LOW:
        return "green"
    if value < THRESHOLD_MEDIUM:
        return "yellow"
    return "red"


def get_value_style(value: float) -> Style:
    """Get a Rich Style for a given value.

    Args:
        value: Value as a percentage (0-100)

    Returns:
        Rich Style with appropriate foreground color
    """
    return Style(color=get_value_color(value))


class Sparkline(Widget):
    """A sparkline widget displaying historical values as a bar graph.

    Displays a horizontal bar graph using Unicode block characters to show
    the history of values over time. Supports configurable width and height,
    as well as color coding based on value thresholds.

    The sparkline automatically scales values to the configured min/max range
    and displays the most recent values within the configured width.

    Attributes:
        values: The historical values to display (most recent last)
        min_value: Minimum value for scaling (default 0.0)
        max_value: Maximum value for scaling (default 100.0)
        width: Number of characters to display (default 30)
        show_label: Whether to show a label prefix (default False)
        label: Label text to show before the sparkline
        color_by_value: Whether to color based on value thresholds (default True)

    Example:
        ```python
        sparkline = Sparkline(width=30, min_value=0, max_value=100)
        sparkline.add_value(25.0)
        sparkline.add_value(50.0)
        sparkline.add_value(75.0)
        # Displays: ▂▄▆
        ```
    """

    DEFAULT_CSS: ClassVar[
        str
    ] = """
    Sparkline {
        width: 100%;
        height: 1;
    }
    """

    # Reactive properties
    min_value: reactive[float] = reactive(0.0)
    max_value: reactive[float] = reactive(100.0)
    width: reactive[int] = reactive(30)
    show_label: reactive[bool] = reactive(False)
    label: reactive[str] = reactive("")
    color_by_value: reactive[bool] = reactive(True)

    def __init__(
        self,
        values: list[float] | None = None,
        min_value: float = 0.0,
        max_value: float = 100.0,
        width: int = 30,
        show_label: bool = False,
        label: str = "",
        color_by_value: bool = True,
        history_size: int = 200,
        *,
        name: str | None = None,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        """Initialize the sparkline widget.

        Args:
            values: Initial list of values (optional)
            min_value: Minimum value for scaling (default 0.0)
            max_value: Maximum value for scaling (default 100.0)
            width: Number of characters to display (default 30)
            show_label: Whether to show a label prefix (default False)
            label: Label text to show before the sparkline
            color_by_value: Whether to color based on value thresholds (default True)
            history_size: Maximum number of values to store (default 60)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.min_value = min_value
        self.max_value = max_value
        self.width = width
        self.show_label = show_label
        self.label = label
        self.color_by_value = color_by_value
        self._history_size = history_size
        self._values: deque[float] = deque(maxlen=history_size)

        # Initialize with provided values
        if values:
            for v in values:
                self._values.append(v)

    @property
    def values(self) -> list[float]:
        """Get the current values as a list."""
        return list(self._values)

    @property
    def history_size(self) -> int:
        """Get the maximum history size."""
        return self._history_size

    def add_value(self, value: float) -> None:
        """Add a new value to the sparkline history.

        The value is appended to the end of the history. If the history
        exceeds the configured size, the oldest value is removed.

        Args:
            value: The new value to add
        """
        self._values.append(value)
        self.refresh()

    def add_values(self, values: list[float]) -> None:
        """Add multiple values to the sparkline history.

        Values are appended in order. If the total exceeds the configured
        history size, the oldest values are removed.

        Args:
            values: List of values to add
        """
        for v in values:
            self._values.append(v)
        self.refresh()

    def set_values(self, values: list[float]) -> None:
        """Replace all values in the sparkline history.

        Args:
            values: New list of values (will be truncated to history_size)
        """
        self._values.clear()
        for v in values:
            self._values.append(v)
        self.refresh()

    def clear(self) -> None:
        """Clear all values from the sparkline."""
        self._values.clear()
        self.refresh()

    def render(self) -> RenderableType:
        """Render the sparkline as a Rich Text object.

        Returns:
            A Rich Text object displaying the sparkline
        """
        result = Text()

        # Add label if configured
        if self.show_label and self.label:
            result.append(f"{self.label}: ", style="dim")

        # Determine display width - use container width if width is 0 (auto mode)
        display_width = self.width
        if display_width <= 0 and self.size.width > 0:
            display_width = self.size.width
        elif display_width <= 0:
            display_width = 30  # fallback default

        # Get the values to display (last 'display_width' values)
        display_values = list(self._values)[-display_width:]

        if not display_values:
            # No data - show placeholder
            result.append("-" * display_width, style="dim")
            return result

        # Determine the color for the sparkline
        # Use the most recent value for coloring
        latest_value = display_values[-1] if display_values else 0.0

        color = get_value_color(latest_value) if self.color_by_value else "white"

        # Build the sparkline characters
        chars = []
        for value in display_values:
            char = value_to_char(value, self.min_value, self.max_value)
            chars.append(char)

        # Pad with spaces if we have fewer values than display width
        padding = display_width - len(chars)
        if padding > 0:
            chars = [" "] * padding + chars

        # Apply color to the sparkline
        sparkline_str = "".join(chars)
        result.append(sparkline_str, style=color)

        return result

    def watch_width(self, new_width: int) -> None:
        """React to width changes.

        Args:
            new_width: The new width value
        """
        self.refresh()

    def watch_min_value(self, new_min: float) -> None:
        """React to min_value changes.

        Args:
            new_min: The new minimum value
        """
        self.refresh()

    def watch_max_value(self, new_max: float) -> None:
        """React to max_value changes.

        Args:
            new_max: The new maximum value
        """
        self.refresh()

    def watch_show_label(self, show: bool) -> None:
        """React to show_label changes.

        Args:
            show: Whether to show the label
        """
        self.refresh()

    def watch_label(self, new_label: str) -> None:
        """React to label changes.

        Args:
            new_label: The new label text
        """
        self.refresh()

    def watch_color_by_value(self, color_enabled: bool) -> None:
        """React to color_by_value changes.

        Args:
            color_enabled: Whether to color by value
        """
        self.refresh()
