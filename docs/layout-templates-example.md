# Layout Template System

The layout template system provides a declarative way to define pane arrangements in uptop's TUI with predefined width and height constraints.

## Width Constraints

Panes can have the following width fractions:
- **Full** (1.0) - Takes entire row width
- **Half** (0.5) - Takes half the row width
- **Quarter** (0.25) - Takes one quarter of the row width
- **Eighth** (0.125) - Takes one eighth of the row width

## Height Constraints

Panes can have the following discrete heights (in terminal lines):
- **Micro** (1 line) - Single line status bar
- **Tiny** (3 lines) - Minimal info (1-2 metrics)
- **Small** (5 lines) - Compact view (3-4 metrics or small graph)
- **Medium** (7 lines) - Standard view (multiple metrics + small graph)
- **Large** (10 lines) - Detailed view (full metrics + graph)
- **XLarge** (20 lines) - Maximum detail (tables, process lists)

## Using Predefined Templates

### Standard Layout (Default)
Balanced layout with all panes visible:
```python
from uptop.tui.layouts import LayoutTemplates

template = LayoutTemplates.get("standard")
layout_config = template.to_layout_config()
```

Layout structure:
```
┌────────────────┬────────────────┐
│  CPU (Half)    │  Memory (Half) │  5 lines
├────────────────┴────────────────┤
│     Processes (Full)            │  20 lines
├────────────────┬────────────────┤
│ Network (Half) │  Disk (Half)   │  5 lines
└────────────────┴────────────────┘
```

### Compact Layout
Compact layout emphasizing the process list:
```
┌──────┬──────┬──────┬──────┐
│ CPU  │ Mem  │ Net  │ Disk │  3 lines (quarter width each)
├──────┴──────┴──────┴──────┤
│      Processes (Full)      │  20 lines
└────────────────────────────┘
```

### Detailed Layout
Larger panes for maximum information:
```
┌────────────────┬────────────────┐
│  CPU (Half)    │  Memory (Half) │  10 lines
├────────────────┴────────────────┤
│     Processes (Full)            │  20 lines
├────────────────┬────────────────┤
│ Network (Half) │  Disk (Half)   │  10 lines
└────────────────┴────────────────┘
```

### Processes-Focused Layout
Maximizes process list space:
```
┌──────┬──────┬──────┬──────┐
│ CPU  │ Mem  │ Net  │ Disk │  1 line (quarter width each)
├──────┴──────┴──────┴──────┤
│      Processes (Full)      │  20 lines
└────────────────────────────┘
```

### Dashboard Layout
Equal-sized panes in a grid:
```
┌────────────────┬────────────────┐
│  CPU (Half)    │  Memory (Half) │  7 lines
├────────────────┼────────────────┤
│ Processes      │  Network       │  7 lines
├────────────────┴────────────────┤
│         Disk (Full)             │  7 lines
└─────────────────────────────────┘
```

## Creating Custom Templates

Define your own layout template:

```python
from uptop.tui.layouts import (
    LayoutTemplate,
    PaneSpec,
    PaneWidth,
    PaneHeight,
    RowSpec,
)

# Create a custom layout
custom_layout = LayoutTemplate(
    name="custom",
    description="My custom layout",
    rows=[
        # First row: three panes
        RowSpec(
            panes=[
                PaneSpec("cpu", PaneWidth.QUARTER, PaneHeight.TINY),
                PaneSpec("memory", PaneWidth.QUARTER, PaneHeight.TINY),
                PaneSpec("network", PaneWidth.HALF, PaneHeight.SMALL),
            ],
        ),
        # Second row: full width processes
        RowSpec(
            panes=[
                PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
            ],
        ),
        # Third row: single pane
        RowSpec(
            panes=[
                PaneSpec("disk", PaneWidth.FULL, PaneHeight.MEDIUM),
            ],
        ),
    ],
)

# Validate the template
valid, message = custom_layout.validate()
if not valid:
    print(f"Invalid layout: {message}")
else:
    # Convert to LayoutConfig for rendering
    layout_config = custom_layout.to_layout_config()
```

## Switching Templates at Runtime

```python
from textual.app import App
from uptop.tui.layouts import GridLayout, LayoutTemplates

class MyApp(App):
    def compose(self):
        # Start with default template
        template = LayoutTemplates.get_default()
        config = template.to_layout_config()
        yield GridLayout(layout_config=config)
    
    def switch_layout(self, template_name: str):
        """Switch to a different layout template."""
        template = LayoutTemplates.get(template_name)
        if template:
            config = template.to_layout_config()
            grid = self.query_one(GridLayout)
            grid.set_layout(config)
```

## Available Templates

List all available templates:

```python
from uptop.tui.layouts import LayoutTemplates

# Get all template names
names = LayoutTemplates.get_names()
# ['standard', 'compact', 'detailed', 'processes-focused', 'split-screen', 'dashboard']

# Get a specific template
template = LayoutTemplates.get("compact")
print(f"{template.name}: {template.description}")
```

## Row Width Validation

The template system validates that pane widths in each row sum to ≤1.0:

```python
# Valid: two halves = 1.0
RowSpec(panes=[
    PaneSpec("cpu", PaneWidth.HALF),
    PaneSpec("memory", PaneWidth.HALF),
])

# Valid: four quarters = 1.0
RowSpec(panes=[
    PaneSpec("cpu", PaneWidth.QUARTER),
    PaneSpec("memory", PaneWidth.QUARTER),
    PaneSpec("network", PaneWidth.QUARTER),
    PaneSpec("disk", PaneWidth.QUARTER),
])

# Invalid: 0.5 + 0.5 + 0.25 = 1.25 > 1.0
RowSpec(panes=[
    PaneSpec("cpu", PaneWidth.HALF),
    PaneSpec("memory", PaneWidth.HALF),
    PaneSpec("network", PaneWidth.QUARTER),  # Exceeds row width!
])
```

## Height Allocation

Row heights are converted to CSS `fr` units proportionally. For example:
- Row with height=5 and row with height=10 → 1fr and 2fr
- Row with height=20 → Takes proportionally more vertical space

The actual line counts are approximate targets; the TUI will scale based on available terminal height.
