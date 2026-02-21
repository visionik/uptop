# Configuration

uptop uses YAML configuration files with sensible defaults. You can run uptop without any configuration -- all settings have default values.

## Config File Locations

Configuration is loaded from the first file found, in this order:

1. `--config PATH` CLI flag
2. `UPTOP_CONFIG_PATH` environment variable
3. `~/.config/uptop/config.yaml` (XDG standard)
4. `~/.uptop/config.yaml` (legacy location)

If no file is found, defaults are used.

## Full Configuration Reference

```yaml
# Core settings
default_mode: tui          # "tui" or "cli"
interval: 1.0              # Global refresh interval in seconds

# TUI settings
tui:
  theme: dark              # dark | light | solarized | nord | gruvbox
  mouse_enabled: true      # Enable mouse support

  # Per-pane configuration
  panes:
    cpu:
      enabled: true
      refresh_interval: 1.0    # Override global interval
      position: [0, 0]         # Grid position [column, row]
      size: [2, 1]             # Grid size [width, height]
    memory:
      enabled: true
      refresh_interval: 2.0
      position: [0, 1]
      size: [1, 1]
    processes:
      enabled: true
      refresh_interval: 2.0
      position: [2, 0]
      size: [2, 2]
      default_sort: cpu_percent   # Sort column
      default_filter: null        # Filter expression
    network:
      enabled: true
      refresh_interval: 1.0
    disk:
      enabled: true
      refresh_interval: 5.0
    gpu:
      enabled: auto            # "auto" to detect GPU availability
      refresh_interval: 1.0
    sensors:
      enabled: true
      refresh_interval: 3.0

  # Layout presets
  layouts:
    default: standard
    custom_layouts:
      server_focus:
        - [cpu, memory]
        - [network, disk]
      dev_focus:
        - [cpu, processes]
        - [memory, disk]

  # Configurable keybindings
  keybindings:
    quit: q
    help: "?"
    filter: /
    kill_process: k
    change_priority: n
    refresh: r
    toggle_tree: t
    next_sort: s

# CLI settings
cli:
  default_format: json         # json | markdown | prometheus
  default_output_mode: once    # once | stream | continuous
  pretty_print: true           # Pretty-print output

# Display preferences
display:
  units:
    memory: binary             # "binary" (KiB/MiB) or "decimal" (KB/MB)
    network: decimal           # "binary" or "decimal"
    temperature: celsius       # "celsius" or "fahrenheit"
  decimal_places: 1
  show_percentages: true

# Plugin settings
plugins:
  directory: ~/.uptop/plugins  # Custom plugin directory
  auto_load: true              # Auto-discover plugins
  enabled_plugins: []          # Explicitly enabled plugins
  plugin_config: {}            # Plugin-specific settings

# Process filter presets
process_filters:
  high_cpu: "cpu_percent > 50"
  high_mem: "memory_mb > 100"
  my_user: "username == '${USER}'"

# Logging (for debugging)
logging:
  enabled: false
  level: INFO                  # DEBUG | INFO | WARNING | ERROR
  file: ~/.uptop/uptop.log
```

## Environment Variable Expansion

Config values support `${VAR}` syntax for environment variable expansion:

```yaml
process_filters:
  my_user: "username == '${USER}'"

plugins:
  directory: "${HOME}/.uptop/plugins"
```

## CLI Overrides

CLI flags override config file values. For example:

```bash
# Config says interval: 1.0, but CLI overrides to 5
uptop --interval 5

# Config says theme: dark, but CLI overrides
uptop --theme nord

# Disable mouse even if config enables it
uptop --no-mouse
```

## Per-Pane Refresh Intervals

Each pane can have its own refresh interval. When the global `--interval` flag is passed on the CLI, it overrides all per-pane intervals:

```yaml
# These per-pane intervals are used by default
tui:
  panes:
    cpu:
      refresh_interval: 1.0     # Fast -- CPU changes rapidly
    disk:
      refresh_interval: 5.0     # Slow -- disk usage changes slowly
```

```bash
# Override all panes to 2 seconds
uptop --interval 2
```

## Disabling Panes

Set `enabled: false` to hide a pane, or use `--panes` to show only specific ones:

```yaml
tui:
  panes:
    sensors:
      enabled: false
```

```bash
# Only show CPU and memory
uptop --panes cpu,memory
```
