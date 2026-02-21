# Changelog

All notable changes to uptop are documented here. This project follows [Conventional Commits](https://www.conventionalcommits.org/).

## 0.1.0 (In Development)

### Features

- **Core Architecture**: Plugin system with discovery via entry points and directory scanning
- **CPU Pane**: Per-core usage, frequency, temperature, load averages with sparklines
- **Memory Pane**: RAM breakdown (total/used/free/cached/buffers), swap usage
- **Process Pane**: Interactive table with sort, filter, tree view, and kill support
- **Network Pane**: Per-interface I/O, active connections, bandwidth graphs
- **Disk Pane**: Filesystem usage per mount, I/O read/write rates and IOPS
- **Site Monitor Pane**: Website uptime monitoring with HTTP status and response times
- **TUI**: Grid-based layout with Textual framework
- **CLI**: JSON, Markdown, and Prometheus output formats
- **Themes**: Dark, Light, Solarized, Nord, Gruvbox
- **Display Modes**: 4-level density modes (Micro, Minimized, Medium, Maximized)
- **Configuration**: YAML-based config with environment variable expansion
- **Web Access**: Serve TUI over HTTP via `uptop serve`
- **Monitoring**: Sentry integration with environment-aware log levels
- **Performance**: Async data collection, ring buffer history, optional profiling

### Platforms

- Linux: Ubuntu 20.04+, Debian 11+, Fedora 36+
- macOS 12+
