# Layout Template Implementation Summary

## Overview

Implemented a declarative layout template system for uptop's TUI that provides tiled window management with predefined width and height constraints.

## Features

### Width Constraints
- **Full** (1.0) - Takes entire row width
- **Half** (0.5) - Takes half the row width  
- **Quarter** (0.25) - Takes one quarter of the row width
- **Eighth** (0.125) - Takes one eighth of the row width

### Height Constraints (in terminal lines)
- **Micro** (1) - Single line status bar
- **Tiny** (3) - Minimal info
- **Small** (5) - Compact view
- **Medium** (7) - Standard view
- **Large** (10) - Detailed view
- **XLarge** (20) - Maximum detail (tables, process lists)

## Architecture

### Core Components

1. **PaneSpec** - Defines a single pane with name, width, and height
2. **RowSpec** - Groups panes horizontally with validation (widths must sum to ≤1.0)
3. **LayoutTemplate** - Complete layout definition with multiple rows
4. **LayoutTemplates** - Registry of predefined templates

### Design Principles

- **Declarative over imperative** - Layouts are defined as data structures, not algorithms
- **Validation at creation** - Ensures widths don't exceed row capacity
- **Stable arrangements** - Users get predictable layouts, not auto-packed surprises
- **Template-based switching** - Easy to define and switch between layouts

## Predefined Templates

Six templates ship with the system:

1. **standard** (default) - Balanced layout with all panes visible
2. **compact** - Emphasizes process list, minimal system stats
3. **detailed** - Larger panes for maximum information
4. **processes-focused** - Maximizes process list space
5. **split-screen** - Vertical split layout
6. **dashboard** - Equal-sized panes in a grid

## Files Created

- `src/uptop/tui/layouts/templates.py` - Template system implementation
- `tests/test_layout_templates.py` - Comprehensive test suite (31 tests, all passing)
- `docs/layout-templates-example.md` - Usage documentation with examples
- `docs/layout-template-implementation.md` - This summary

## Files Modified

- `src/uptop/tui/layouts/__init__.py` - Added exports for template system

## Usage Example

```python
from uptop.tui.layouts import LayoutTemplates

# Get a template
template = LayoutTemplates.get("compact")

# Convert to LayoutConfig for GridLayout
config = template.to_layout_config()

# Use with GridLayout
grid = GridLayout(layout_config=config)
```

## Creating Custom Templates

```python
from uptop.tui.layouts import (
    LayoutTemplate,
    PaneSpec,
    PaneWidth,
    PaneHeight,
    RowSpec,
)

custom = LayoutTemplate(
    name="custom",
    description="My custom layout",
    rows=[
        RowSpec(panes=[
            PaneSpec("cpu", PaneWidth.QUARTER, PaneHeight.TINY),
            PaneSpec("memory", PaneWidth.QUARTER, PaneHeight.TINY),
            PaneSpec("network", PaneWidth.HALF, PaneHeight.SMALL),
        ]),
        RowSpec(panes=[
            PaneSpec("processes", PaneWidth.FULL, PaneHeight.XLARGE),
        ]),
    ],
)

# Validate before use
valid, msg = custom.validate()
if valid:
    config = custom.to_layout_config()
```

## Integration with Existing System

The template system integrates seamlessly with the existing GridLayout:

- Templates convert to `LayoutConfig` objects
- `GridLayout.set_layout()` can switch templates at runtime
- Existing CSS and rendering logic works unchanged
- Backward compatible with existing code

## Testing

All 31 tests pass:
- PaneSpec default and custom values
- RowSpec validation (empty, valid, exceeds width)
- RowSpec height calculation
- LayoutTemplate validation
- LayoutTemplate to LayoutConfig conversion
- All predefined templates validate correctly
- LayoutTemplates registry operations
- Width and height enum values

## Next Steps

To integrate with the application:

1. **Add keyboard shortcut** to cycle through templates (e.g., `l` key)
2. **Add config option** to set default template
3. **Add CLI flag** `--layout=template_name` to start with specific template
4. **Persist selection** - Remember user's last template choice
5. **Dynamic templates** - Allow users to define custom templates in config file

## Benefits

- **Predictable** - Users know what layout they'll get
- **Flexible** - Easy to add new templates without code changes
- **Validated** - Impossible to create invalid layouts (widths overflow)
- **Type-safe** - Enums ensure only valid widths/heights used
- **Testable** - Pure data structures, easy to test
- **Maintainable** - Templates live in one place, easy to update
