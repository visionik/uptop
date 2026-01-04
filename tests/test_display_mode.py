"""Tests for pane display modes."""

import pytest

from uptop.models.base import DisplayMode


class TestDisplayModeEnum:
    """Tests for DisplayMode enum."""

    def test_has_three_values(self) -> None:
        """Test enum has MINIMUM, MEDIUM, MAXIMUM."""
        assert len(DisplayMode) == 3
        assert DisplayMode.MINIMUM.value == "minimum"
        assert DisplayMode.MEDIUM.value == "medium"
        assert DisplayMode.MAXIMUM.value == "maximum"

    def test_next_cycles_correctly(self) -> None:
        """Test next() cycles through modes."""
        assert DisplayMode.MINIMUM.next() == DisplayMode.MEDIUM
        assert DisplayMode.MEDIUM.next() == DisplayMode.MAXIMUM
        assert DisplayMode.MAXIMUM.next() == DisplayMode.MINIMUM

    def test_full_cycle(self) -> None:
        """Test cycling through all modes returns to start."""
        mode = DisplayMode.MINIMUM
        mode = mode.next()  # MEDIUM
        mode = mode.next()  # MAXIMUM
        mode = mode.next()  # MINIMUM
        assert mode == DisplayMode.MINIMUM

    def test_is_string_enum(self) -> None:
        """Test DisplayMode is a string enum."""
        assert isinstance(DisplayMode.MINIMUM, str)
        assert DisplayMode.MINIMUM == "minimum"


class TestPaneContainerDisplayMode:
    """Tests for PaneContainer display mode tracking."""

    def test_default_mode_is_medium(self) -> None:
        """Test default display mode is MEDIUM."""
        from uptop.tui.widgets.pane_container import PaneContainer

        container = PaneContainer(title="Test")
        assert container.display_mode == DisplayMode.MEDIUM

    def test_cycle_display_mode(self) -> None:
        """Test cycling through display modes."""
        from uptop.tui.widgets.pane_container import PaneContainer

        container = PaneContainer(title="Test")
        assert container.display_mode == DisplayMode.MEDIUM

        new_mode = container.cycle_display_mode()
        assert new_mode == DisplayMode.MAXIMUM
        assert container.display_mode == DisplayMode.MAXIMUM

        new_mode = container.cycle_display_mode()
        assert new_mode == DisplayMode.MINIMUM
        assert container.display_mode == DisplayMode.MINIMUM

        new_mode = container.cycle_display_mode()
        assert new_mode == DisplayMode.MEDIUM
        assert container.display_mode == DisplayMode.MEDIUM

    def test_get_pane_name_with_valid_id(self) -> None:
        """Test _get_pane_name extracts name correctly."""
        from uptop.tui.widgets.pane_container import PaneContainer

        container = PaneContainer(title="Test", id="pane-cpu")
        assert container._get_pane_name() == "cpu"

        container2 = PaneContainer(title="Test", id="pane-memory")
        assert container2._get_pane_name() == "memory"

    def test_get_pane_name_with_invalid_id(self) -> None:
        """Test _get_pane_name returns empty string for invalid IDs."""
        from uptop.tui.widgets.pane_container import PaneContainer

        container = PaneContainer(title="Test", id="other-id")
        assert container._get_pane_name() == ""

        container2 = PaneContainer(title="Test")  # No ID
        assert container2._get_pane_name() == ""


class TestDisplayModeMessages:
    """Tests for display mode messages."""

    def test_display_mode_changed_message(self) -> None:
        """Test DisplayModeChanged message."""
        from uptop.tui.messages import DisplayModeChanged

        msg = DisplayModeChanged("cpu")
        assert msg.pane_name == "cpu"

    def test_pane_resized_message(self) -> None:
        """Test PaneResized message."""
        from uptop.tui.messages import PaneResized

        msg = PaneResized("memory", 80, 24)
        assert msg.pane_name == "memory"
        assert msg.width == 80
        assert msg.height == 24


class TestDisplayModeKeybinding:
    """Tests for 'm' keybinding."""

    def test_m_binding_exists(self) -> None:
        """Test 'm' binding exists in app."""
        from uptop.tui.app import UptopApp

        bindings = [b for b in UptopApp.BINDINGS if b.key == "m"]
        assert len(bindings) == 1
        assert bindings[0].action == "cycle_display_mode"


class TestRenderTuiSignature:
    """Tests for updated render_tui signature."""

    def test_cpu_pane_accepts_size_and_mode(self) -> None:
        """Test CPUPane.render_tui accepts size and mode."""
        from unittest.mock import MagicMock

        from uptop.plugins.cpu import CPUData, CPUPane

        pane = CPUPane()
        pane.initialize()

        # Create mock data
        data = MagicMock(spec=CPUData)
        data.cores = []
        data.total_usage_percent = 50.0

        # Should not raise when called with size and mode
        widget = pane.render_tui(data, size=(80, 24), mode=DisplayMode.MAXIMUM)
        # Just verify it returns something (Label for invalid data in this case)
        assert widget is not None

    def test_memory_pane_accepts_size_and_mode(self) -> None:
        """Test MemoryPane.render_tui accepts size and mode."""
        from textual.widgets import Label

        from uptop.plugins.memory import MemoryPane

        pane = MemoryPane()

        # Pass invalid data to get a Label (simpler test)
        # The point is to test the signature accepts size and mode
        widget = pane.render_tui("invalid", size=(80, 24), mode=DisplayMode.MINIMUM)
        assert widget is not None
        assert isinstance(widget, Label)

    def test_backward_compatibility_without_args(self) -> None:
        """Test render_tui works without size and mode (backward compat)."""
        from unittest.mock import MagicMock

        from uptop.plugins.cpu import CPUData, CPUPane

        pane = CPUPane()
        pane.initialize()

        data = MagicMock(spec=CPUData)
        data.cores = []

        # Should work with just data argument
        widget = pane.render_tui(data)
        assert widget is not None
