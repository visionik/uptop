# Configuration Schema

Complete reference for `~/.config/uptop/config.yaml`.

## Top-Level Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_mode` | string | `"tui"` | Default mode: `"tui"` or `"cli"` |
| `interval` | float | `1.0` | Global refresh interval in seconds |
| `tui` | object | | TUI-specific settings |
| `cli` | object | | CLI-specific settings |
| `display` | object | | Display preferences |
| `plugins` | object | | Plugin configuration |
| `process_filters` | object | | Named process filter presets |
| `logging` | object | | Logging configuration |

## `tui`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `theme` | string | `"dark"` | Theme name: `dark`, `light`, `solarized`, `nord`, `gruvbox` |
| `mouse_enabled` | bool | `true` | Enable mouse support |
| `panes` | object | | Per-pane settings |
| `layouts` | object | | Layout presets |
| `keybindings` | object | | Keyboard shortcut overrides |

## `tui.panes.<name>`

Each pane accepts:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool/string | `true` | Enable pane (`true`, `false`, or `"auto"` for GPU) |
| `refresh_interval` | float | varies | Per-pane refresh interval in seconds |
| `position` | [int, int] | auto | Grid position `[column, row]` |
| `size` | [int, int] | auto | Grid size `[width, height]` |

### Pane-specific settings

**processes:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_sort` | string | `"cpu_percent"` | Default sort column |
| `default_filter` | string | `null` | Default filter expression |

### Default refresh intervals

| Pane | Default Interval |
|------|-----------------|
| `cpu` | 1.0s |
| `memory` | 2.0s |
| `processes` | 2.0s |
| `network` | 1.0s |
| `disk` | 5.0s |
| `gpu` | 1.0s |
| `sensors` | 3.0s |

## `tui.layouts`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default` | string | `"standard"` | Active layout preset name |
| `custom_layouts` | object | | Named layout definitions (arrays of pane rows) |

## `tui.keybindings`

| Key | Default | Description |
|-----|---------|-------------|
| `quit` | `"q"` | Quit application |
| `help` | `"?"` | Toggle help screen |
| `filter` | `"/"` | Open filter dialog |
| `kill_process` | `"k"` | Kill selected process |
| `change_priority` | `"n"` | Change process priority |
| `refresh` | `"r"` | Refresh all panes |
| `toggle_tree` | `"t"` | Toggle tree view |
| `next_sort` | `"s"` | Cycle sort column |

## `cli`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_format` | string | `"json"` | Output format: `json`, `markdown`, `prometheus` |
| `default_output_mode` | string | `"once"` | Output mode: `once`, `stream`, `continuous` |
| `pretty_print` | bool | `true` | Pretty-print JSON output |

## `display`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `decimal_places` | int | `1` | Number of decimal places for values |
| `show_percentages` | bool | `true` | Show percentage values |

### `display.units`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `memory` | string | `"binary"` | `"binary"` (KiB/MiB) or `"decimal"` (KB/MB) |
| `network` | string | `"decimal"` | `"binary"` or `"decimal"` |
| `temperature` | string | `"celsius"` | `"celsius"` or `"fahrenheit"` |

## `plugins`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `directory` | string | `"~/.uptop/plugins"` | Custom plugin directory |
| `auto_load` | bool | `true` | Auto-discover plugins |
| `enabled_plugins` | list | `[]` | Explicitly enabled plugin names |
| `plugin_config` | object | `{}` | Plugin-specific settings keyed by plugin name |

## `process_filters`

Named filter presets. Values are filter expressions:

```yaml
process_filters:
  high_cpu: "cpu_percent > 50"
  high_mem: "memory_mb > 100"
  my_user: "username == '${USER}'"
```

## `logging`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable file logging |
| `level` | string | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `file` | string | `"~/.uptop/uptop.log"` | Log file path |

## Environment Variable Expansion

All string values support `${VAR}` syntax:

```yaml
plugins:
  directory: "${HOME}/.uptop/plugins"
process_filters:
  my_user: "username == '${USER}'"
```
