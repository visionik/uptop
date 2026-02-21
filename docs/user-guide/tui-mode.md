# TUI Mode

The TUI (Terminal User Interface) is uptop's default mode when running in an interactive terminal. It provides a real-time, full-screen monitoring dashboard built with [Textual](https://textual.textualize.io/).

## Starting the TUI

```bash
# Auto-detected when running in a terminal
uptop

# Explicit TUI mode
uptop tui

# With options
uptop tui --theme nord --interval 2 --no-mouse
```

## Layout

The default layout arranges panes in a grid:

```
+------------------+------------------+
|       CPU        |     Processes    |
+------------------+                  |
|      Memory      |                  |
+------------------+------------------+
|     Network      |       Disk       |
+------------------+------------------+
```

Panes auto-refresh at their configured intervals. The layout adapts to your terminal size.

## Panes

### CPU Pane

Displays per-core CPU usage with progress bars, current frequency, temperature (when available), and 1/5/15 minute load averages. Includes sparkline history graphs when space allows.

### Memory Pane

Shows RAM breakdown (total, used, free, available, cached, buffers) with progress bars, plus swap usage. On macOS, shows wired/active/inactive breakdown when available.

### Process Pane

Interactive process table with columns: PID, User, CPU%, MEM%, VSZ, RSS, State, Runtime, Command. Supports sorting, filtering, tree view, and process kill.

### Network Pane

Per-interface network I/O showing bytes and packets sent/received, errors, drops, and bandwidth rates. Active TCP/UDP connections table with address, port, state, and PID.

### Disk Pane

Filesystem usage per mount point with used/free/total and percentage bars. I/O performance showing read/write rates and IOPS per disk.

### Site Monitor Pane

Website uptime monitoring showing HTTP status, response time in milliseconds, and up/down status for configured URLs.

## Display Modes

Each pane supports 4 display density modes. Press `m` while a pane is focused to cycle through them:

| Mode | Description |
|------|-------------|
| **Micro** | Ultra-compact single-line or icon view |
| **Minimized** | Essential information only |
| **Medium** | Balanced view (default) |
| **Maximized** | Full detail with all available data |

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| `q` | Quit uptop |
| `?` | Toggle help screen |
| `r` | Refresh all panes immediately |
| `Tab` | Focus next pane |
| `Shift+Tab` | Focus previous pane |
| `m` | Cycle display mode on focused pane |

### Process Pane

| Key | Action |
|-----|--------|
| `s` | Cycle sort column |
| `/` | Open filter dialog |
| `k` | Kill selected process (with confirmation) |
| `t` | Toggle tree view |

### Mouse Support

Mouse support is enabled by default:

- Click a pane to focus it
- Click a process row to select it
- Scroll the process list with the mouse wheel
- Disable with `--no-mouse` or `tui.mouse_enabled: false` in config

## Themes

uptop ships with 5 built-in themes:

| Theme | Description |
|-------|-------------|
| `dark` | Default dark theme |
| `light` | Light background theme |
| `solarized` | Solarized color palette |
| `nord` | Nord color palette |
| `gruvbox` | Gruvbox color palette |

Set via CLI flag:

```bash
uptop --theme solarized
```

Or in config:

```yaml
tui:
  theme: solarized
```

## Web Access

Serve the TUI over HTTP using Textual Serve:

```bash
uptop serve --port 8000 --host localhost
```

This makes the full TUI accessible from a web browser at `http://localhost:8000`.

## Startup Behavior

On launch, uptop:

1. Loads configuration (CLI flags override config file)
2. Discovers and initializes plugins
3. Renders the grid layout with a fade-in animation
4. Starts per-pane async refresh loops
5. Shows the footer with available keybindings

If a pane fails to collect data, it shows an error state while other panes continue updating normally.
