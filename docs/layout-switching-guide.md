# Layout Switching Guide

## Quick Start

Press **`l`** (lowercase L) to cycle through layout templates while running uptop.

## Available Layouts

The application cycles through these layouts in order:

1. **standard** - Default balanced layout with all panes visible
2. **compact** - Compact layout with smaller panes, processes emphasized
3. **detailed** - Detailed layout with larger panes for maximum information
4. **processes-focused** - Maximizes space for process list with minimal system stats
5. **split-screen** - Split screen with processes on left, system stats on right
6. **dashboard** - Dashboard-style layout with equal-sized panes

## Keyboard Shortcut

| Key | Action | Description |
|-----|--------|-------------|
| `l` | Cycle Layout | Switch to the next layout template |

## What Happens When You Switch

1. The layout immediately changes to show the new arrangement
2. A notification displays the new layout name and description
3. All panes refresh with the new dimensions
4. Focus remains on the currently focused pane (if it still exists)

## Example Layouts

### Standard (Default)
```
┌────────────────┬────────────────┐
│  CPU (Half)    │  Memory (Half) │  5 lines
├────────────────┴────────────────┤
│     Processes (Full)            │  20 lines
├────────────────┬────────────────┤
│ Network (Half) │  Disk (Half)   │  5 lines
└────────────────┴────────────────┘
```

### Compact
```
┌──────┬──────┬──────┬──────┐
│ CPU  │ Mem  │ Net  │ Disk │  3 lines (quarter width)
├──────┴──────┴──────┴──────┤
│      Processes (Full)      │  20 lines
└────────────────────────────┘
```

### Processes-Focused
```
┌──────┬──────┬──────┬──────┐
│ CPU  │ Mem  │ Net  │ Disk │  1 line (quarter width)
├──────┴──────┴──────┴──────┤
│      Processes (Full)      │  20+ lines
└────────────────────────────┘
```

## Implementation Details

### In the Application Code

The `UptopApp` class handles layout switching:

```python
async def action_cycle_layout(self) -> None:
    """Cycle through available layout templates."""
    from uptop.tui.layouts.templates import LayoutTemplates
    
    # Get all available layouts
    layout_names = LayoutTemplates.get_names()
    
    # Cycle to next
    self._current_layout_index = (self._current_layout_index + 1) % len(layout_names)
    layout_name = layout_names[self._current_layout_index]
    
    # Get template and switch
    template = LayoutTemplates.get(layout_name)
    config = template.to_layout_config()
    
    grid = self.query_one(GridLayout)
    grid.set_layout(config)
    
    # Refresh all panes
    await self.refresh_all_panes()
```

### Binding

The binding is defined in `UptopApp.BINDINGS`:

```python
Binding("l", "cycle_layout", "Layout"),
```

## Programmatic Access

You can also switch layouts programmatically:

```python
from uptop.tui.layouts.templates import LayoutTemplates

# Get a specific layout
template = LayoutTemplates.get("compact")
config = template.to_layout_config()

# Apply to grid
grid.set_layout(config)
```

## Future Enhancements

Potential future additions:

1. **Direct layout selection** - Press `L` (shift+l) to show a menu of all layouts
2. **Config file default** - Set default layout in `~/.uptop/config.yaml`
3. **Persist selection** - Remember last used layout across sessions
4. **Custom layouts** - Define custom templates in config file
5. **Per-pane visibility** - Toggle individual panes on/off within a layout

## Related Files

- `src/uptop/tui/app.py` - Application with layout switching action
- `src/uptop/tui/layouts/templates.py` - Template definitions
- `src/uptop/tui/layouts/grid.py` - GridLayout widget that renders templates
