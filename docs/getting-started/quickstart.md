# Quick Start

## Launch the TUI

Run `uptop` with no arguments to start the interactive terminal dashboard:

```bash
uptop
```

This opens a full-screen monitoring dashboard with CPU, Memory, Processes, Network, and Disk panes arranged in a grid layout.

### Navigate the TUI

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Cycle focus between panes |
| `q` | Quit |
| `?` | Show help screen |
| `r` | Refresh all panes immediately |
| `m` | Cycle display density mode on focused pane |

### Process Management

When the process pane is focused:

| Key | Action |
|-----|--------|
| `s` | Cycle sort column (CPU% -> MEM% -> PID -> ...) |
| `/` | Open filter dialog |
| `k` | Kill selected process (with confirmation) |
| `t` | Toggle tree view |

Mouse clicks also work for selecting panes and process rows.

## CLI Mode

Get a single JSON snapshot of system metrics:

```bash
uptop --json --once
```

Stream metrics continuously in Prometheus format:

```bash
uptop --prometheus --stream --interval 5
```

Output a Markdown-formatted report:

```bash
uptop --markdown --once
```

Monitor only specific panes:

```bash
uptop --json --once --panes cpu,memory
```

## Choose a Theme

```bash
uptop --theme nord
```

Available themes: `dark` (default), `light`, `solarized`, `nord`, `gruvbox`.

## Web Access

Serve the TUI as a web application accessible from a browser:

```bash
uptop serve --port 8000
```

Then open `http://localhost:8000` in your browser.

## Configuration

Create a config file at `~/.config/uptop/config.yaml`:

```yaml
default_mode: tui
interval: 1.0

tui:
  theme: nord
  mouse_enabled: true
  panes:
    cpu:
      enabled: true
      refresh_interval: 1.0
    memory:
      enabled: true
      refresh_interval: 2.0
    processes:
      enabled: true
      default_sort: cpu_percent

cli:
  default_format: json
  pretty_print: true
```

See the [Configuration Guide](../user-guide/configuration.md) for all options.

## Next Steps

- [TUI Mode Guide](../user-guide/tui-mode.md) -- detailed TUI features and navigation
- [CLI Mode Guide](../user-guide/cli-mode.md) -- all output formats and scripting options
- [Configuration Reference](../user-guide/configuration.md) -- full config schema
- [Plugin Development](../plugins/overview.md) -- extend uptop with custom panes
