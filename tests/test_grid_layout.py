"""Tests for the GridLayout widget.

This module tests the GridLayout widget functionality including:
- Layout creation and configuration
- Pane arrangement in rows and columns
- Focus cycling (Tab/Shift+Tab)
- Pane visibility toggling
- Layout configuration changes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from textual.app import App, ComposeResult
from textual.binding import Binding

from uptop.config import Config, load_config
from uptop.tui.layouts.grid import (
    DEFAULT_LAYOUT_CONFIG,
    GridLayout,
    GridRow,
    LayoutConfig,
    PanePosition,
    PlaceholderContent,
)
from uptop.tui.widgets.pane_container import PaneContainer

if TYPE_CHECKING:
    pass


class GridLayoutTestApp(App[None]):
    """Test app for GridLayout widget testing."""

    def __init__(
        self,
        layout_config: LayoutConfig | None = None,
        config: Config | None = None,
    ) -> None:
        """Initialize test app with configurable grid layout.

        Args:
            layout_config: Optional layout configuration
            config: Optional application configuration
        """
        super().__init__()
        self._layout_config = layout_config
        self._config = config

    def compose(self) -> ComposeResult:
        """Compose the test app with a GridLayout."""
        yield GridLayout(
            layout_config=self._layout_config,
            config=self._config,
            id="test-grid",
        )


class TestPanePosition:
    """Tests for PanePosition dataclass."""

    def test_pane_position_initialization(self) -> None:
        """Test PanePosition initializes with correct values."""
        pos = PanePosition(name="cpu", row=0, col=0)
        assert pos.name == "cpu"
        assert pos.row == 0
        assert pos.col == 0
        assert pos.row_span == 1  # default
        assert pos.col_span == 0.5  # default
        assert pos.height_weight == 1  # default

    def test_pane_position_with_custom_values(self) -> None:
        """Test PanePosition with custom values."""
        pos = PanePosition(
            name="processes",
            row=1,
            col=0,
            row_span=2,
            col_span=1.0,
            height_weight=3,
        )
        assert pos.name == "processes"
        assert pos.row == 1
        assert pos.col == 0
        assert pos.row_span == 2
        assert pos.col_span == 1.0
        assert pos.height_weight == 3


class TestLayoutConfig:
    """Tests for LayoutConfig dataclass."""

    def test_layout_config_initialization(self) -> None:
        """Test LayoutConfig initializes with correct defaults."""
        config = LayoutConfig(name="test")
        assert config.name == "test"
        assert config.panes == []
        assert config.row_heights == []

    def test_layout_config_with_panes(self) -> None:
        """Test LayoutConfig with panes."""
        panes = [
            PanePosition(name="cpu", row=0, col=0),
            PanePosition(name="memory", row=0, col=1),
        ]
        config = LayoutConfig(name="test", panes=panes)
        assert len(config.panes) == 2
        assert config.panes[0].name == "cpu"
        assert config.panes[1].name == "memory"

    def test_get_pane_names_returns_ordered_list(self) -> None:
        """Test get_pane_names returns panes in row-column order."""
        panes = [
            PanePosition(name="network", row=1, col=0),
            PanePosition(name="cpu", row=0, col=0),
            PanePosition(name="memory", row=0, col=1),
            PanePosition(name="disk", row=1, col=1),
        ]
        config = LayoutConfig(name="test", panes=panes)
        names = config.get_pane_names()
        assert names == ["cpu", "memory", "network", "disk"]

    def test_get_rows_groups_panes_by_row(self) -> None:
        """Test get_rows groups panes by row index."""
        panes = [
            PanePosition(name="cpu", row=0, col=0),
            PanePosition(name="memory", row=0, col=1),
            PanePosition(name="processes", row=1, col=0),
            PanePosition(name="network", row=2, col=0),
            PanePosition(name="disk", row=2, col=1),
        ]
        config = LayoutConfig(name="test", panes=panes)
        rows = config.get_rows()

        assert len(rows) == 3
        assert len(rows[0]) == 2  # cpu, memory
        assert len(rows[1]) == 1  # processes
        assert len(rows[2]) == 2  # network, disk

        assert rows[0][0].name == "cpu"
        assert rows[0][1].name == "memory"
        assert rows[1][0].name == "processes"
        assert rows[2][0].name == "network"
        assert rows[2][1].name == "disk"

    def test_get_rows_empty_config(self) -> None:
        """Test get_rows with empty panes list."""
        config = LayoutConfig(name="empty")
        rows = config.get_rows()
        assert rows == []


class TestDefaultLayoutConfig:
    """Tests for the default layout configuration."""

    def test_default_layout_has_correct_name(self) -> None:
        """Test default layout has 'standard' name."""
        assert DEFAULT_LAYOUT_CONFIG.name == "standard"

    def test_default_layout_has_five_panes(self) -> None:
        """Test default layout has all five core panes."""
        assert len(DEFAULT_LAYOUT_CONFIG.panes) == 5

    def test_default_layout_pane_names(self) -> None:
        """Test default layout has correct pane names."""
        names = DEFAULT_LAYOUT_CONFIG.get_pane_names()
        assert "cpu" in names
        assert "memory" in names
        assert "processes" in names
        assert "network" in names
        assert "disk" in names

    def test_default_layout_has_three_rows(self) -> None:
        """Test default layout has three rows."""
        rows = DEFAULT_LAYOUT_CONFIG.get_rows()
        assert len(rows) == 3

    def test_default_layout_top_row(self) -> None:
        """Test default layout top row has CPU and Memory."""
        rows = DEFAULT_LAYOUT_CONFIG.get_rows()
        top_row = rows[0]
        assert len(top_row) == 2
        names = [p.name for p in top_row]
        assert "cpu" in names
        assert "memory" in names

    def test_default_layout_middle_row(self) -> None:
        """Test default layout middle row has Processes (full width)."""
        rows = DEFAULT_LAYOUT_CONFIG.get_rows()
        middle_row = rows[1]
        assert len(middle_row) == 1
        assert middle_row[0].name == "processes"
        assert middle_row[0].col_span == 1.0

    def test_default_layout_bottom_row(self) -> None:
        """Test default layout bottom row has Network and Disk."""
        rows = DEFAULT_LAYOUT_CONFIG.get_rows()
        bottom_row = rows[2]
        assert len(bottom_row) == 2
        names = [p.name for p in bottom_row]
        assert "network" in names
        assert "disk" in names

    def test_default_layout_row_heights(self) -> None:
        """Test default layout has correct row heights (processes is taller)."""
        assert DEFAULT_LAYOUT_CONFIG.row_heights == [1, 2, 1]


class TestPlaceholderContent:
    """Tests for PlaceholderContent widget."""

    def test_placeholder_content_initialization(self) -> None:
        """Test PlaceholderContent initializes correctly."""
        placeholder = PlaceholderContent("cpu")
        assert placeholder._pane_name == "cpu"

    def test_placeholder_content_render(self) -> None:
        """Test PlaceholderContent renders pane name."""
        placeholder = PlaceholderContent("memory")
        rendered = placeholder.render()
        assert "[memory]" in rendered
        assert "Pane content will appear here" in rendered


class TestGridLayout:
    """Tests for GridLayout widget instantiation."""

    def test_grid_layout_initialization_default(self) -> None:
        """Test GridLayout initializes with default config."""
        layout = GridLayout()
        assert layout.layout_config is DEFAULT_LAYOUT_CONFIG
        assert layout._config is None

    def test_grid_layout_initialization_with_custom_config(self) -> None:
        """Test GridLayout initializes with custom layout config."""
        custom_config = LayoutConfig(
            name="custom",
            panes=[PanePosition(name="cpu", row=0, col=0, col_span=1.0)],
        )
        layout = GridLayout(layout_config=custom_config)
        assert layout.layout_config is custom_config

    def test_grid_layout_initialization_with_app_config(self) -> None:
        """Test GridLayout initializes with application config."""
        config = load_config()
        layout = GridLayout(config=config)
        assert layout._config is config

    def test_focus_order_property_returns_copy(self) -> None:
        """Test focus_order returns a copy of the list."""
        layout = GridLayout()
        order1 = layout.focus_order
        order2 = layout.focus_order
        # Should be equal but not the same object
        assert order1 is not order2

    def test_visible_panes_initially_all(self) -> None:
        """Test all panes are visible initially."""
        layout = GridLayout()
        # Before compose, _focus_order is empty
        # After compose, it should have all panes
        assert layout._hidden_panes == set()


class TestGridLayoutRendering:
    """Integration tests for GridLayout rendering using Textual pilot."""

    @pytest.mark.asyncio
    async def test_renders_with_default_layout(self) -> None:
        """Test GridLayout renders with default layout."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)
            assert grid is not None

    @pytest.mark.asyncio
    async def test_creates_all_pane_containers(self) -> None:
        """Test GridLayout creates all pane containers."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            panes = app.query(PaneContainer)
            # Default layout has 5 panes
            assert len(panes) == 5

    @pytest.mark.asyncio
    async def test_pane_containers_have_correct_ids(self) -> None:
        """Test pane containers have correct IDs."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            for name in ["cpu", "memory", "processes", "network", "disk"]:
                pane = app.query_one(f"#pane-{name}", PaneContainer)
                assert pane is not None

    @pytest.mark.asyncio
    async def test_creates_grid_rows(self) -> None:
        """Test GridLayout creates GridRow containers."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            rows = app.query(GridRow)
            # Default layout has 3 rows
            assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_grid_rows_have_correct_ids(self) -> None:
        """Test grid rows have correct IDs."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            for idx in range(3):
                row = app.query_one(f"#grid-row-{idx}", GridRow)
                assert row is not None

    @pytest.mark.asyncio
    async def test_processes_row_has_larger_height(self) -> None:
        """Test processes row has larger height weight."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            middle_row = app.query_one("#grid-row-1", GridRow)
            assert "row-weight-2" in middle_row.classes

    @pytest.mark.asyncio
    async def test_get_pane_returns_correct_container(self) -> None:
        """Test get_pane returns the correct PaneContainer."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)
            cpu_pane = grid.get_pane("cpu")
            assert cpu_pane is not None
            assert cpu_pane.id == "pane-cpu"

    @pytest.mark.asyncio
    async def test_get_pane_returns_none_for_invalid(self) -> None:
        """Test get_pane returns None for invalid pane name."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)
            invalid_pane = grid.get_pane("invalid")
            assert invalid_pane is None


class TestGridLayoutCustomConfig:
    """Tests for GridLayout with custom configurations."""

    @pytest.mark.asyncio
    async def test_renders_with_single_pane(self) -> None:
        """Test GridLayout renders with single pane configuration."""
        config = LayoutConfig(
            name="single",
            panes=[PanePosition(name="cpu", row=0, col=0, col_span=1.0)],
        )
        app = GridLayoutTestApp(layout_config=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            panes = app.query(PaneContainer)
            assert len(panes) == 1

    @pytest.mark.asyncio
    async def test_renders_with_custom_row_heights(self) -> None:
        """Test GridLayout respects custom row heights."""
        config = LayoutConfig(
            name="custom",
            panes=[
                PanePosition(name="cpu", row=0, col=0),
                PanePosition(name="memory", row=1, col=0),
            ],
            row_heights=[1, 3],
        )
        app = GridLayoutTestApp(layout_config=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            row1 = app.query_one("#grid-row-1", GridRow)
            # Height weight 3 is capped at 3
            assert "row-weight-3" in row1.classes


class TestFocusCycling:
    """Tests for focus cycling functionality."""

    @pytest.mark.asyncio
    async def test_focus_order_matches_layout(self) -> None:
        """Test focus order matches the layout order."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)
            order = grid.focus_order
            # Default order: cpu, memory, processes, network, disk
            assert order == ["cpu", "memory", "processes", "network", "disk"]

    @pytest.mark.asyncio
    async def test_focus_next_pane_cycles_forward(self) -> None:
        """Test Tab moves focus to next pane."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # Initial focus should be on first pane
            assert grid._current_focus_index == 0

            # Press Tab to move to next
            grid.action_focus_next_pane()
            assert grid._current_focus_index == 1

            grid.action_focus_next_pane()
            assert grid._current_focus_index == 2

    @pytest.mark.asyncio
    async def test_focus_next_pane_wraps_around(self) -> None:
        """Test Tab wraps from last pane to first."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # Move to last pane
            grid._current_focus_index = 4  # disk (last)

            # Press Tab to wrap around
            grid.action_focus_next_pane()
            assert grid._current_focus_index == 0  # cpu (first)

    @pytest.mark.asyncio
    async def test_focus_previous_pane_cycles_backward(self) -> None:
        """Test Shift+Tab moves focus to previous pane."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # Move to second pane first
            grid._current_focus_index = 2

            # Press Shift+Tab to move back
            grid.action_focus_previous_pane()
            assert grid._current_focus_index == 1

            grid.action_focus_previous_pane()
            assert grid._current_focus_index == 0

    @pytest.mark.asyncio
    async def test_focus_previous_pane_wraps_around(self) -> None:
        """Test Shift+Tab wraps from first pane to last."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # Focus is on first pane
            grid._current_focus_index = 0

            # Press Shift+Tab to wrap around
            grid.action_focus_previous_pane()
            assert grid._current_focus_index == 4  # disk (last)

    @pytest.mark.asyncio
    async def test_focus_bindings_exist(self) -> None:
        """Test focus cycling bindings exist."""
        grid = GridLayout()
        # Filter to get only Binding instances with the keys we care about
        bindings = [
            b for b in grid.BINDINGS if isinstance(b, Binding) and b.key in ("tab", "shift+tab")
        ]
        assert len(bindings) == 2

        tab_binding = next(b for b in bindings if b.key == "tab")
        assert tab_binding.action == "focus_next_pane"

        shift_tab_binding = next(b for b in bindings if b.key == "shift+tab")
        assert shift_tab_binding.action == "focus_previous_pane"


class TestPaneVisibility:
    """Tests for pane visibility toggling."""

    @pytest.mark.asyncio
    async def test_hide_pane(self) -> None:
        """Test hiding a pane."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # All panes visible initially
            assert grid.is_pane_visible("cpu")

            # Hide cpu pane
            result = grid.hide_pane("cpu")
            assert result is True
            assert not grid.is_pane_visible("cpu")
            assert "cpu" in grid._hidden_panes

    @pytest.mark.asyncio
    async def test_show_pane(self) -> None:
        """Test showing a hidden pane."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # Hide then show
            grid.hide_pane("memory")
            assert not grid.is_pane_visible("memory")

            result = grid.show_pane("memory")
            assert result is True
            assert grid.is_pane_visible("memory")

    @pytest.mark.asyncio
    async def test_toggle_pane_hides_visible(self) -> None:
        """Test toggle_pane hides a visible pane."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            result = grid.toggle_pane("cpu")
            assert result is False  # Now hidden
            assert not grid.is_pane_visible("cpu")

    @pytest.mark.asyncio
    async def test_toggle_pane_shows_hidden(self) -> None:
        """Test toggle_pane shows a hidden pane."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            grid.hide_pane("cpu")
            result = grid.toggle_pane("cpu")
            assert result is True  # Now visible
            assert grid.is_pane_visible("cpu")

    @pytest.mark.asyncio
    async def test_hide_pane_returns_false_if_already_hidden(self) -> None:
        """Test hide_pane returns False if pane is already hidden."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            grid.hide_pane("cpu")
            result = grid.hide_pane("cpu")
            assert result is False

    @pytest.mark.asyncio
    async def test_show_pane_returns_false_if_already_visible(self) -> None:
        """Test show_pane returns False if pane is already visible."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            result = grid.show_pane("cpu")
            assert result is False

    @pytest.mark.asyncio
    async def test_visible_panes_excludes_hidden(self) -> None:
        """Test visible_panes excludes hidden panes."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            grid.hide_pane("cpu")
            grid.hide_pane("memory")

            visible = grid.visible_panes
            assert "cpu" not in visible
            assert "memory" not in visible
            assert "processes" in visible
            assert "network" in visible
            assert "disk" in visible

    @pytest.mark.asyncio
    async def test_focus_cycling_skips_hidden_panes(self) -> None:
        """Test focus cycling skips hidden panes."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            # Hide memory (second pane)
            grid.hide_pane("memory")

            # Focus should be on cpu
            grid._current_focus_index = 0

            # Next should skip memory and go to processes
            grid.action_focus_next_pane()
            visible = grid.visible_panes
            # Index 1 in visible is now processes
            assert visible[grid._current_focus_index] == "processes"


class TestGetVisiblePaneWidgets:
    """Tests for get_visible_pane_widgets method."""

    @pytest.mark.asyncio
    async def test_returns_all_panes_when_none_hidden(self) -> None:
        """Test returns all pane widgets when none are hidden."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            widgets = grid.get_visible_pane_widgets()
            assert len(widgets) == 5

    @pytest.mark.asyncio
    async def test_excludes_hidden_panes(self) -> None:
        """Test excludes hidden panes from result."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            grid.hide_pane("cpu")
            grid.hide_pane("disk")

            widgets = grid.get_visible_pane_widgets()
            assert len(widgets) == 3

            widget_ids = [w.id for w in widgets]
            assert "pane-cpu" not in widget_ids
            assert "pane-disk" not in widget_ids
            assert "pane-memory" in widget_ids
            assert "pane-processes" in widget_ids
            assert "pane-network" in widget_ids


class TestSetLayout:
    """Tests for set_layout method."""

    @pytest.mark.asyncio
    async def test_set_layout_changes_config(self) -> None:
        """Test set_layout changes the layout configuration."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            new_config = LayoutConfig(
                name="minimal",
                panes=[
                    PanePosition(name="cpu", row=0, col=0, col_span=1.0),
                    PanePosition(name="memory", row=1, col=0, col_span=1.0),
                ],
            )
            grid.set_layout(new_config)

            assert grid.layout_config is new_config

    @pytest.mark.asyncio
    async def test_set_layout_clears_hidden_panes(self) -> None:
        """Test set_layout clears hidden panes set."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            grid.hide_pane("cpu")
            assert len(grid._hidden_panes) > 0

            new_config = LayoutConfig(
                name="minimal",
                panes=[PanePosition(name="cpu", row=0, col=0, col_span=1.0)],
            )
            grid.set_layout(new_config)

            assert len(grid._hidden_panes) == 0

    @pytest.mark.asyncio
    async def test_set_layout_resets_focus_index(self) -> None:
        """Test set_layout resets focus index to 0."""
        app = GridLayoutTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)

            grid._current_focus_index = 3

            new_config = LayoutConfig(
                name="minimal",
                panes=[PanePosition(name="cpu", row=0, col=0, col_span=1.0)],
            )
            grid.set_layout(new_config)

            assert grid._current_focus_index == 0


class TestGridLayoutCSS:
    """Tests for GridLayout CSS styling."""

    def test_grid_layout_has_default_css(self) -> None:
        """Test GridLayout has default CSS defined."""
        assert GridLayout.DEFAULT_CSS is not None
        assert "GridLayout" in GridLayout.DEFAULT_CSS
        assert "row-weight" in GridLayout.DEFAULT_CSS

    def test_grid_row_has_default_css(self) -> None:
        """Test GridRow has default CSS defined."""
        assert GridRow.DEFAULT_CSS is not None
        assert "GridRow" in GridRow.DEFAULT_CSS

    def test_placeholder_content_has_default_css(self) -> None:
        """Test PlaceholderContent has default CSS defined."""
        assert PlaceholderContent.DEFAULT_CSS is not None
        assert "PlaceholderContent" in PlaceholderContent.DEFAULT_CSS


class TestGridLayoutWithAppConfig:
    """Tests for GridLayout with application configuration."""

    @pytest.mark.asyncio
    async def test_uses_pane_refresh_interval_from_config(self) -> None:
        """Test pane containers use refresh interval from config."""
        config = load_config(
            cli_overrides={
                "tui": {
                    "panes": {
                        "cpu": {"refresh_interval": 2.5},
                    }
                }
            }
        )
        app = GridLayoutTestApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.query_one("#test-grid", GridLayout)
            cpu_pane = grid.get_pane("cpu")
            assert cpu_pane is not None
            assert cpu_pane.refresh_interval == 2.5
