# uptop - Universal Performance & Telemetry Output

A modern CLI+TUI system monitoring tool written in Python that provides btop-like functionality with extensibility and multiple output formats.

## Features

- **Dual Mode**: Interactive TUI and scriptable CLI with structured output
- **Plugin Architecture**: Extensible via Python plugins (entry points + local directory)
- **Multiple Formats**: JSON, Markdown, and Prometheus output for integration
- **Modern Stack**: Python 3.11+, Textual TUI, Pydantic data models, psutil
- **OpenTelemetry Integration**: Built-in OTLP HTTP receiver for monitoring Claude Code telemetry

## Panes

| Pane | Description |
|------|-------------|
| CPU | Per-core usage, frequency, temperature, load averages |
| Memory | RAM and swap usage with progress bars |
| Processes | Sortable, filterable process list with kill support |
| Network | Per-interface bandwidth and connection stats |
| Disk | Partition usage and I/O statistics |
| OpenTelemetry | Claude Code telemetry: tokens, cost, sessions, events |
| Site Monitor | Website uptime and response time monitoring |

## Quick Start

### Installation

```bash
# Clone and install in development mode
git clone https://github.com/jsgoecke/uptop.git
cd uptop
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Usage

```bash
# Launch TUI (default)
uptop

# Single JSON snapshot
uptop --json --once

# Continuous JSON output
uptop --json --stream
```

### OpenTelemetry Pane

The OpenTelemetry pane receives OTLP HTTP telemetry from tools like Claude Code. To enable:

1. Start uptop (the OTLP receiver starts automatically on `127.0.0.1:4318`)
2. Configure your tool to export OTLP data:

```bash
# For Claude Code
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

The pane displays token usage, cost, session activity, and a live event log. Configure the receiver in `~/.config/uptop/config.yaml`:

```yaml
tui:
  panes:
    otel:
      enabled: true
      refresh_interval: 2.0
      host: "127.0.0.1"
      port: 4318
```

## Configuration

Default config location: `~/.config/uptop/config.yaml`

```yaml
default_mode: tui
interval: 1.0

tui:
  theme: dark
  mouse_enabled: true
  panes:
    cpu: {enabled: true, refresh_interval: 1.0}
    memory: {enabled: true, refresh_interval: 2.0}
    processes: {enabled: true, default_sort: cpu_percent}
    otel: {enabled: true, refresh_interval: 2.0, port: 4318}
```

## Keyboard Shortcuts

| Key | Action | Scope |
|-----|--------|-------|
| q | Quit | Global |
| ? | Help | Global |
| r | Refresh | Global |
| Tab | Next pane | Global |
| / | Filter | Process |
| s | Sort | Process |
| k | Kill | Process |
| t | Tree view | Process |

## Architecture

```
UI Layer:     TUI (Textual)  |  CLI (Typer)
Plugin Layer: Discovery -> Registry -> Lifecycle
Plugin API:   PanePlugin | CollectorPlugin | FormatterPlugin | ActionPlugin
Internal:     CPU | Memory | Process | Network | Disk | OTel | Site Monitor
Collection:   psutil + aiohttp (OTLP) + httpx (HTTP checks)
```

Each pane is a plugin with three layers: **Data Model** (Pydantic) -> **Collector** (async) -> **Widget** (Textual). Panes support 4 display modes: micro, minimized, medium, and maximized.

## Development

```bash
# Run all quality checks
task check

# Run tests
task test

# Run tests with coverage
task test:coverage

# Format code
task fmt

# Lint
task lint
```

## Documentation

- [Project Specification](./SPECIFICATION.md) - Technical specification and implementation plan
- [Contributing Guide](./CONTRIBUTING.md) - Development setup and contribution guidelines

## Dependencies

**Core**: psutil, textual, typer, pydantic, PyYAML, aiohttp

**Optional**: `pip install uptop[gpu]` for GPU support, `pip install uptop[otel]` for OpenTelemetry proto definitions

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.
