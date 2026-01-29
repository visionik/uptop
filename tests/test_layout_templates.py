"""Tests for layout template system."""

import pytest

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


class TestPaneSpec:
    """Tests for PaneSpec dataclass."""

    def test_default_values(self):
        """Test that default values are applied correctly."""
        spec = PaneSpec(name="cpu")
        assert spec.name == "cpu"
        assert spec.width == PaneWidth.HALF
        assert spec.height == PaneHeight.MEDIUM

    def test_custom_values(self):
        """Test that custom values are stored correctly."""
        spec = PaneSpec(
            name="processes",
            width=PaneWidth.FULL,
            height=PaneHeight.XLARGE,
        )
        assert spec.name == "processes"
        assert spec.width == PaneWidth.FULL
        assert spec.height == PaneHeight.XLARGE


class TestRowSpec:
    """Tests for RowSpec dataclass."""

    def test_validation_empty_row(self):
        """Test that empty rows are invalid."""
        row = RowSpec(panes=[])
        valid, msg = row.validate()
        assert not valid
        assert "at least one pane" in msg

    def test_validation_valid_half_widths(self):
        """Test that two half-width panes are valid."""
        row = RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.HALF),
                PaneSpec("memory", PaneWidth.HALF),
            ]
        )
        valid, msg = row.validate()
        assert valid
        assert msg == ""

    def test_validation_valid_quarter_widths(self):
        """Test that four quarter-width panes are valid."""
        row = RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.QUARTER),
                PaneSpec("memory", PaneWidth.QUARTER),
                PaneSpec("network", PaneWidth.QUARTER),
                PaneSpec("disk", PaneWidth.QUARTER),
            ]
        )
        valid, msg = row.validate()
        assert valid

    def test_validation_invalid_exceeds_width(self):
        """Test that widths exceeding 1.0 are invalid."""
        row = RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.HALF),
                PaneSpec("memory", PaneWidth.HALF),
                PaneSpec("network", PaneWidth.QUARTER),
            ]
        )
        valid, msg = row.validate()
        assert not valid
        assert "must be ≤1.0" in msg

    def test_get_height_explicit(self):
        """Test that explicit height is used when set."""
        row = RowSpec(
            panes=[PaneSpec("cpu", height=PaneHeight.SMALL)],
            height=PaneHeight.LARGE,
        )
        assert row.get_height() == PaneHeight.LARGE

    def test_get_height_from_panes(self):
        """Test that max pane height is used when no explicit height."""
        row = RowSpec(
            panes=[
                PaneSpec("cpu", height=PaneHeight.SMALL),
                PaneSpec("memory", height=PaneHeight.LARGE),
                PaneSpec("network", height=PaneHeight.TINY),
            ]
        )
        assert row.get_height() == PaneHeight.LARGE


class TestLayoutTemplate:
    """Tests for LayoutTemplate dataclass."""

    def test_validation_empty_template(self):
        """Test that templates without rows are invalid."""
        template = LayoutTemplate(
            name="empty",
            description="Empty template",
            rows=[],
        )
        valid, msg = template.validate()
        assert not valid
        assert "at least one row" in msg

    def test_validation_invalid_row(self):
        """Test that templates with invalid rows are invalid."""
        template = LayoutTemplate(
            name="invalid",
            description="Invalid template",
            rows=[
                RowSpec(panes=[]),  # Invalid: empty row
            ],
        )
        valid, msg = template.validate()
        assert not valid
        assert "Row 0" in msg

    def test_validation_valid_template(self):
        """Test that valid templates pass validation."""
        template = LayoutTemplate(
            name="valid",
            description="Valid template",
            rows=[
                RowSpec(panes=[PaneSpec("cpu", PaneWidth.FULL)]),
            ],
        )
        valid, msg = template.validate()
        assert valid

    def test_to_layout_config(self):
        """Test conversion to LayoutConfig."""
        template = LayoutTemplate(
            name="test",
            description="Test template",
            rows=[
                RowSpec(
                    panes=[
                        PaneSpec("cpu", PaneWidth.HALF, PaneHeight.SMALL),
                        PaneSpec("memory", PaneWidth.HALF, PaneHeight.SMALL),
                    ]
                ),
                RowSpec(
                    panes=[
                        PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
                    ]
                ),
            ],
        )

        config = template.to_layout_config()
        assert config.name == "test"
        assert len(config.panes) == 3
        assert config.row_heights == [5, 20]

        # Check first row panes
        assert config.panes[0].name == "cpu"
        assert config.panes[0].row == 0
        assert config.panes[0].col == 0
        assert config.panes[0].col_span == 0.5

        assert config.panes[1].name == "memory"
        assert config.panes[1].row == 0
        assert config.panes[1].col == 1
        assert config.panes[1].col_span == 0.5

        # Check second row pane
        assert config.panes[2].name == "processes"
        assert config.panes[2].row == 1
        assert config.panes[2].col == 0
        assert config.panes[2].col_span == 1.0


class TestPredefinedTemplates:
    """Tests for predefined layout templates."""

    @pytest.mark.parametrize(
        "template",
        [
            STANDARD_LAYOUT,
            COMPACT_LAYOUT,
            DETAILED_LAYOUT,
            PROCESSES_FOCUSED,
            SPLIT_SCREEN,
            DASHBOARD,
        ],
    )
    def test_template_valid(self, template):
        """Test that all predefined templates are valid."""
        valid, msg = template.validate()
        assert valid, f"Template {template.name} is invalid: {msg}"

    @pytest.mark.parametrize(
        "template",
        [
            STANDARD_LAYOUT,
            COMPACT_LAYOUT,
            DETAILED_LAYOUT,
            PROCESSES_FOCUSED,
            SPLIT_SCREEN,
            DASHBOARD,
        ],
    )
    def test_template_converts_to_config(self, template):
        """Test that all predefined templates convert to LayoutConfig."""
        config = template.to_layout_config()
        assert config.name == template.name
        assert len(config.panes) > 0
        assert len(config.row_heights) == len(template.rows)


class TestLayoutTemplates:
    """Tests for LayoutTemplates registry."""

    def test_get_existing_template(self):
        """Test getting an existing template."""
        template = LayoutTemplates.get("standard")
        assert template is not None
        assert template.name == "standard"

    def test_get_nonexistent_template(self):
        """Test getting a nonexistent template returns None."""
        template = LayoutTemplates.get("nonexistent")
        assert template is None

    def test_get_names(self):
        """Test getting all template names."""
        names = LayoutTemplates.get_names()
        assert "standard" in names
        assert "compact" in names
        assert "detailed" in names
        assert "processes-focused" in names
        assert "split-screen" in names
        assert "dashboard" in names

    def test_get_default(self):
        """Test getting the default template."""
        template = LayoutTemplates.get_default()
        assert template is not None
        assert template.name == "standard"


class TestWidthAndHeightEnums:
    """Tests for PaneWidth and PaneHeight enums."""

    def test_pane_widths(self):
        """Test that pane width values are correct."""
        assert PaneWidth.FULL.value == 1.0
        assert PaneWidth.HALF.value == 0.5
        assert PaneWidth.QUARTER.value == 0.25
        assert PaneWidth.EIGHTH.value == 0.125

    def test_pane_heights(self):
        """Test that pane height values are correct."""
        assert PaneHeight.MICRO.value == 1
        assert PaneHeight.TINY.value == 3
        assert PaneHeight.SMALL.value == 5
        assert PaneHeight.MEDIUM.value == 7
        assert PaneHeight.LARGE.value == 10
        assert PaneHeight.XLARGE.value == 20

    def test_widths_sum_to_one(self):
        """Test that common width combinations sum to 1.0."""
        # Two halves
        assert PaneWidth.HALF.value + PaneWidth.HALF.value == 1.0

        # Four quarters
        assert PaneWidth.QUARTER.value * 4 == 1.0

        # Eight eighths
        assert PaneWidth.EIGHTH.value * 8 == 1.0

        # Half + quarter + quarter
        assert PaneWidth.HALF.value + PaneWidth.QUARTER.value + PaneWidth.QUARTER.value == 1.0
