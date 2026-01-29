"""Layout templates for uptop TUI.

This module provides a declarative system for defining pane layouts with:
- Predefined width fractions (full=1.0, half=0.5, quarter=0.25, eighth=0.125)
- Discrete height values (1, 3, 5, 7, 10, 20+ lines)
- Template-based layouts that users can switch between
- Validation of row constraints (widths must sum to ≤1.0)

Templates define stable, predictable arrangements rather than auto-packing,
which provides better UX for system monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from uptop.tui.layouts.grid import LayoutConfig, PanePosition


class PaneWidth(float, Enum):
    """Standard pane width fractions.

    These are the allowed width values for panes in a row.
    Widths in a row must sum to ≤1.0.
    """

    FULL = 1.0
    HALF = 0.5
    QUARTER = 0.25
    EIGHTH = 0.125


class PaneHeight(int, Enum):
    """Standard pane heights in terminal lines.

    These are discrete height values that work well for different
    types of content. Actual height is allocated using CSS fr units
    proportionally.
    """

    MICRO = 1  # Single line (status bar)
    TINY = 3  # Minimal info (1-2 metrics)
    SMALL = 5  # Compact view (3-4 metrics or small graph)
    MEDIUM = 7  # Standard view (multiple metrics + small graph)
    LARGE = 10  # Detailed view (full metrics + graph)
    XLARGE = 20  # Maximum detail (tables, process lists)


@dataclass
class PaneSpec:
    """Specification for a pane in a layout template.

    Attributes:
        name: Pane identifier (e.g., "cpu", "memory", "processes")
        width: Width fraction from PaneWidth enum
        height: Height in lines from PaneHeight enum
    """

    name: str
    width: PaneWidth = PaneWidth.HALF
    height: PaneHeight = PaneHeight.MEDIUM


@dataclass
class RowSpec:
    """Specification for a row of panes.

    A row contains one or more panes arranged horizontally.
    The sum of pane widths must be ≤1.0.

    Attributes:
        panes: List of pane specifications in this row
        height: Height for the entire row (max of pane heights)
    """

    panes: list[PaneSpec] = field(default_factory=list)
    height: PaneHeight | None = None  # If None, use max of pane heights

    def validate(self) -> tuple[bool, str]:
        """Validate that the row configuration is valid.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.panes:
            return False, "Row must contain at least one pane"

        # Check width sum
        total_width = sum(pane.width.value for pane in self.panes)
        if total_width > 1.0 + 1e-6:  # Small epsilon for float comparison
            return False, f"Row widths sum to {total_width:.3f}, must be ≤1.0"

        return True, ""

    def get_height(self) -> PaneHeight:
        """Get the effective height for this row.

        Returns:
            The row height (explicit or max of pane heights)
        """
        if self.height is not None:
            return self.height

        if not self.panes:
            return PaneHeight.MEDIUM

        # Use the tallest pane height
        return max((pane.height for pane in self.panes), default=PaneHeight.MEDIUM)


@dataclass
class LayoutTemplate:
    """A complete layout template defining pane arrangement.

    Templates provide stable, predictable layouts that users can
    switch between. Each template is a list of rows.

    Attributes:
        name: Template name (e.g., "standard", "compact", "detailed")
        description: Human-readable description
        rows: List of row specifications
    """

    name: str
    description: str
    rows: list[RowSpec] = field(default_factory=list)

    def validate(self) -> tuple[bool, str]:
        """Validate the entire template.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.rows:
            return False, "Template must contain at least one row"

        for idx, row in enumerate(self.rows):
            valid, msg = row.validate()
            if not valid:
                return False, f"Row {idx}: {msg}"

        return True, ""

    def to_layout_config(self) -> LayoutConfig:
        """Convert this template to a LayoutConfig for rendering.

        Returns:
            LayoutConfig object compatible with GridLayout
        """
        panes: list[PanePosition] = []
        row_heights: list[int] = []

        for row_idx, row in enumerate(self.rows):
            row_height = row.get_height()
            row_heights.append(row_height.value)

            for col_idx, pane_spec in enumerate(row.panes):
                panes.append(
                    PanePosition(
                        name=pane_spec.name,
                        row=row_idx,
                        col=col_idx,
                        col_span=pane_spec.width.value,
                        height_weight=row_height.value,
                    )
                )

        return LayoutConfig(
            name=self.name,
            panes=panes,
            row_heights=row_heights,
        )


# Predefined layout templates

STANDARD_LAYOUT = LayoutTemplate(
    name="standard",
    description="Default balanced layout with all panes visible",
    rows=[
        RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.HALF, PaneHeight.SMALL),
                PaneSpec("memory", PaneWidth.HALF, PaneHeight.SMALL),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("network", PaneWidth.HALF, PaneHeight.SMALL),
                PaneSpec("disk", PaneWidth.HALF, PaneHeight.SMALL),
            ],
        ),
    ],
)

COMPACT_LAYOUT = LayoutTemplate(
    name="compact",
    description="Compact layout with smaller panes, processes emphasized",
    rows=[
        RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.QUARTER, PaneHeight.TINY),
                PaneSpec("memory", PaneWidth.QUARTER, PaneHeight.TINY),
                PaneSpec("network", PaneWidth.QUARTER, PaneHeight.TINY),
                PaneSpec("disk", PaneWidth.QUARTER, PaneHeight.TINY),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
            ],
        ),
    ],
)

DETAILED_LAYOUT = LayoutTemplate(
    name="detailed",
    description="Detailed layout with larger panes for maximum information",
    rows=[
        RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.HALF, PaneHeight.LARGE),
                PaneSpec("memory", PaneWidth.HALF, PaneHeight.LARGE),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("network", PaneWidth.HALF, PaneHeight.LARGE),
                PaneSpec("disk", PaneWidth.HALF, PaneHeight.LARGE),
            ],
        ),
    ],
)

PROCESSES_FOCUSED = LayoutTemplate(
    name="processes-focused",
    description="Maximizes space for process list with minimal system stats",
    rows=[
        RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.QUARTER, PaneHeight.MICRO),
                PaneSpec("memory", PaneWidth.QUARTER, PaneHeight.MICRO),
                PaneSpec("network", PaneWidth.QUARTER, PaneHeight.MICRO),
                PaneSpec("disk", PaneWidth.QUARTER, PaneHeight.MICRO),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
            ],
            height=PaneHeight.XLARGE,
        ),
    ],
)

SPLIT_SCREEN = LayoutTemplate(
    name="split-screen",
    description="Split screen with processes on left, system stats on right",
    rows=[
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.HALF, PaneHeight.XLARGE),
                # Right side gets a vertical stack (simulated with half-width)
                PaneSpec("cpu", PaneWidth.HALF, PaneHeight.MEDIUM),
            ],
        ),
        RowSpec(
            panes=[
                # Spacer to align with processes (half width)
                PaneSpec("network", PaneWidth.HALF, PaneHeight.MEDIUM),
                PaneSpec("memory", PaneWidth.HALF, PaneHeight.MEDIUM),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("disk", PaneWidth.HALF, PaneHeight.MEDIUM),
            ],
        ),
    ],
)

DASHBOARD = LayoutTemplate(
    name="dashboard",
    description="Dashboard-style layout with equal-sized panes",
    rows=[
        RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.HALF, PaneHeight.MEDIUM),
                PaneSpec("memory", PaneWidth.HALF, PaneHeight.MEDIUM),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.HALF, PaneHeight.MEDIUM),
                PaneSpec("network", PaneWidth.HALF, PaneHeight.MEDIUM),
            ],
        ),
        RowSpec(
            panes=[
                PaneSpec("disk", PaneWidth.FULL, PaneHeight.MEDIUM),
            ],
        ),
    ],
)


class LayoutTemplates:
    """Registry of all available layout templates."""

    ALL: ClassVar[dict[str, LayoutTemplate]] = {
        "standard": STANDARD_LAYOUT,
        "compact": COMPACT_LAYOUT,
        "detailed": DETAILED_LAYOUT,
        "processes-focused": PROCESSES_FOCUSED,
        "split-screen": SPLIT_SCREEN,
        "dashboard": DASHBOARD,
    }

    @classmethod
    def get(cls, name: str) -> LayoutTemplate | None:
        """Get a layout template by name.

        Args:
            name: Template name

        Returns:
            LayoutTemplate if found, None otherwise
        """
        return cls.ALL.get(name)

    @classmethod
    def get_names(cls) -> list[str]:
        """Get list of all template names.

        Returns:
            List of template names
        """
        return list(cls.ALL.keys())

    @classmethod
    def get_default(cls) -> LayoutTemplate:
        """Get the default layout template.

        Returns:
            The standard layout template
        """
        return STANDARD_LAYOUT
