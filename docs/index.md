# uptop - Universal Performance & Telemetry Output

A modern CLI+TUI system monitoring tool written in Python that provides btop-like functionality with extensibility via a plugin architecture and multiple output formats.

## What is uptop?

uptop is a system monitoring tool that runs in two modes:

- **TUI Mode** -- An interactive, real-time dashboard in your terminal with grid-based panes, color themes, mouse support, and keyboard navigation.
- **CLI Mode** -- Scriptable output in JSON, Markdown, or Prometheus format for integration with monitoring pipelines and automation.

## Core Monitoring Panes

| Pane | Metrics |
|------|---------|
| **CPU** | Per-core usage, frequency, temperature, load averages |
| **Memory** | RAM total/used/free/cached, swap, visual bars |
| **Processes** | PID, user, CPU%, MEM%, state, runtime, command; sort/filter/kill |
| **Network** | Per-interface I/O rates, active connections, bandwidth graphs |
| **Disk** | Filesystem usage per mount, I/O read/write rates, IOPS |
| **Site Monitor** | Website uptime, HTTP status codes, response times |

## Key Features

- **Plugin Architecture** -- Extend uptop with custom panes, collectors, formatters, and actions
- **Multiple Output Formats** -- JSON, Markdown, and Prometheus for CLI integrations
- **5 Built-in Themes** -- Dark, Light, Solarized, Nord, Gruvbox
- **4 Display Density Modes** -- Micro, Minimized, Medium, Maximized
- **Configurable** -- YAML config with per-pane intervals, keybindings, layout presets
- **Async Throughout** -- Non-blocking data collection with graceful per-pane failure handling
- **Cross-Platform** -- Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+) and macOS 12+

## Quick Links

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [TUI Mode Guide](user-guide/tui-mode.md)
- [CLI Mode Guide](user-guide/cli-mode.md)
- [Configuration Reference](user-guide/configuration.md)
- [Plugin Development](plugins/overview.md)
- [CLI Reference](reference/cli.md)
- [Contributing](community/contributing.md)
