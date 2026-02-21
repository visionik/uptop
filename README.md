# uptop - Universal Performance & Telemetry Output

A modern CLI+TUI system monitoring tool written in Python that provides btop-like functionality with a plugin architecture and multiple output formats (JSON, Markdown, Prometheus).

## Features

- **Dual Mode** -- Interactive TUI dashboard and scriptable CLI with structured output
- **6 Monitoring Panes** -- CPU, Memory, Processes, Network, Disk, Site Monitor
- **Plugin Architecture** -- Extend with custom panes, collectors, formatters, and actions
- **Multiple Output Formats** -- JSON, Markdown, and Prometheus for monitoring pipelines
- **5 Themes** -- Dark, Light, Solarized, Nord, Gruvbox
- **4 Display Modes** -- Micro, Minimized, Medium, Maximized density per pane
- **Configurable** -- YAML config with per-pane intervals, keybindings, layout presets
- **Web Access** -- Serve the TUI in a browser via `uptop serve`
- **Cross-Platform** -- Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+) and macOS 12+

## Quick Start

### Install from PyPI

```bash
pip install uptop
```

### Install from Source

```bash
git clone https://github.com/jsgoecke/uptop.git
cd uptop
pip install .
```

### Optional Extras

```bash
pip install uptop[gpu]    # NVIDIA/AMD GPU monitoring
pip install uptop[query]  # JMESPath query filtering
pip install uptop[all]    # All optional dependencies
```

### Run

```bash
# Interactive TUI (default)
uptop

# Single JSON snapshot
uptop --json --once

# Stream Prometheus metrics
uptop --prometheus --stream --interval 5

# Markdown report
uptop --markdown --once
```

### TUI Navigation

| Key | Action |
|-----|--------|
| `q` | Quit |
| `?` | Help screen |
| `r` | Refresh all panes |
| `Tab` / `Shift+Tab` | Cycle pane focus |
| `m` | Cycle display density mode |
| `s` | Sort processes |
| `/` | Filter processes |
| `k` | Kill process (with confirmation) |
| `t` | Toggle tree view |

Mouse clicks and scrolling are also supported (disable with `--no-mouse`).

## CLI Examples

```bash
# CPU and memory only, piped to jq
uptop --json --once --panes cpu,memory | jq '.panes.cpu.load_avg'

# Prometheus textfile collector
uptop --prometheus --once > /var/lib/node_exporter/textfile/uptop.prom

# Serve TUI in a browser
uptop serve --port 8000
```

## Configuration

Create `~/.config/uptop/config.yaml`:

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
    disk:
      refresh_interval: 5.0

cli:
  default_format: json
  pretty_print: true
```

See the full [Configuration Reference](docs/user-guide/configuration.md).

## Themes

Set with `--theme` or in config under `tui.theme`:

| Theme | Description |
|-------|-------------|
| `dark` | Default dark theme |
| `light` | Light background |
| `solarized` | Solarized color palette |
| `nord` | Nord arctic colors |
| `gruvbox` | Warm retro palette |

## Plugin System

uptop is built on a plugin architecture. The core panes are plugins themselves. Extend uptop with:

- **Pane Plugins** -- New monitoring panels
- **Collector Plugins** -- Additional data for existing panes
- **Formatter Plugins** -- Custom output formats
- **Action Plugins** -- Keyboard-triggered operations

Plugins are discovered via Python entry points or from `~/.uptop/plugins/`.

See the [Plugin Development Guide](docs/plugins/overview.md).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| TUI | [Textual](https://textual.textualize.io/) |
| CLI | [Typer](https://typer.tiangolo.com/) |
| Data Models | [Pydantic](https://docs.pydantic.dev/) v2 |
| System Info | [psutil](https://github.com/giampaolo/psutil) |
| Config | PyYAML |
| Testing | pytest with 75%+ coverage |
| Quality | ruff, black, isort, mypy (strict) |

## Documentation

All documentation lives in [`docs/`](docs/):

- [Installation](docs/getting-started/installation.md)
- [Quick Start](docs/getting-started/quickstart.md)
- [TUI Mode Guide](docs/user-guide/tui-mode.md)
- [CLI Mode Guide](docs/user-guide/cli-mode.md)
- [Configuration](docs/user-guide/configuration.md)
- [Themes & Customization](docs/user-guide/customization.md)
- [Plugin Development](docs/plugins/overview.md)
- [CLI Reference](docs/reference/cli.md)
- [Config Schema](docs/reference/config-schema.md)
- [Keyboard Shortcuts](docs/reference/keyboard-shortcuts.md)
- [Prometheus Metrics](docs/reference/prometheus-metrics.md)
- [Project Specification](docs/specification.md)
- [Contributing](docs/community/contributing.md)
- [Changelog](docs/community/changelog.md)

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/yourusername/uptop.git
cd uptop
python -m venv .venv && source .venv/bin/activate
task install

# Run quality checks (format, lint, type check, test, coverage)
task check
```

See [Contributing](docs/community/contributing.md) for the full development workflow.

## License

MIT License -- see [LICENSE](LICENSE) for details.
