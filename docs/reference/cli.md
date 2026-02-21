# CLI Reference

## Synopsis

```
uptop [OPTIONS]
uptop tui [OPTIONS]
uptop cli [OPTIONS]
uptop serve [OPTIONS]
```

## Global Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--config` | `-c` | PATH | auto | Path to config file |
| `--interval` | `-i` | FLOAT | 1.0 | Refresh interval in seconds (0.1-3600) |
| `--panes` | `-p` | TEXT | all | Comma-separated list of panes to enable |
| `--version` | `-V` | | | Show version and exit |
| `--check-plugins` | | | | Validate all registered plugins and exit |
| `--debug` | | | | Enable performance profiling and debug output |
| `--help` | | | | Show help and exit |

## Commands

### `uptop` (default)

Auto-detects mode: TUI if running in an interactive terminal, CLI otherwise. Format and stream flags override detection.

### `uptop tui`

Run the interactive TUI dashboard.

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--theme` | `-t` | ENUM | dark | Color theme: dark, light, solarized, nord, gruvbox |
| `--layout` | `-l` | TEXT | standard | Layout preset name |
| `--no-mouse` | | | | Disable mouse support |
| `--debug` | | | | Enable performance profiling |

### `uptop cli`

Run in CLI mode with structured output.

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--json` | `-j` | | | Output in JSON format |
| `--markdown` | `-m` | | | Output in Markdown format |
| `--prometheus` | | | | Output in Prometheus format |
| `--once` | `-o` | | | Single snapshot then exit |
| `--stream` | `-s` | | | Continuous streaming (NDJSON) |
| `--continuous` | | | | ANSI in-place redraw |
| `--pretty/--no-pretty` | | | true | Pretty-print output |
| `--query` | `-q` | TEXT | | JMESPath filter expression |

### `uptop serve`

Serve the TUI as a web application via HTTP.

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--port` | `-p` | INT | 8000 | Port to serve on |
| `--host` | `-H` | TEXT | localhost | Host to bind to |

## Mode Detection Logic

1. Explicit subcommand (`tui` / `cli` / `serve`) takes precedence
2. Format flags (`--json`, `--markdown`, `--prometheus`) imply CLI mode
3. Stream flags (`--stream`, `--continuous`) imply CLI mode
4. TTY detection: TUI if stdin+stdout are a terminal, CLI otherwise

## Environment Variables

| Variable | Description |
|----------|-------------|
| `UPTOP_CONFIG_PATH` | Override default config file path |
| `UPTOP_ENV` | Set environment: `dev`, `development`, `production` |
| `UPTOP_LOG_LEVEL` | Override log level |
| `UPTOP_LOG_FILE` | Override log file path |
| `UPTOP_PLUGINS_DIR` | Override plugin directory |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration error, plugin error, or runtime failure |
| 130 | Interrupted by SIGINT (Ctrl+C) |

## Examples

```bash
# Interactive monitoring
uptop
uptop tui --theme nord

# Single JSON snapshot
uptop --json --once

# Stream Prometheus metrics every 5 seconds
uptop --prometheus --stream --interval 5

# Only CPU and memory, compact JSON
uptop --json --once --panes cpu,memory --no-pretty

# Filter JSON with JMESPath
uptop --json --once --query "panes.cpu.load_avg"

# Serve on all interfaces
uptop serve --host 0.0.0.0 --port 9090

# Validate plugins
uptop --check-plugins

# Debug performance
uptop tui --debug
```
