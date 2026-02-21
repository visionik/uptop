# Keyboard Shortcuts

All keyboard shortcuts can be customized in `~/.config/uptop/config.yaml` under `tui.keybindings`.

## Global Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| `q` | Quit | Exit uptop |
| `?` | Help | Toggle the help screen overlay |
| `r` | Refresh | Force immediate refresh of all panes |
| `Tab` | Next Pane | Move focus to the next pane |
| `Shift+Tab` | Prev Pane | Move focus to the previous pane |
| `m` | Mode | Cycle display density mode on focused pane |

## Process Pane Shortcuts

Active when the process pane is focused:

| Key | Action | Description |
|-----|--------|-------------|
| `s` | Sort | Cycle sort column: CPU% -> MEM% -> PID -> User -> Command |
| `/` | Filter | Open filter dialog to search processes |
| `k` | Kill | Kill selected process (shows confirmation dialog) |
| `t` | Tree | Toggle between flat list and tree (parent-child) view |

## Kill Confirmation Dialog

When killing a process (`k`):

- Shows process PID, name, and command
- Choose signal: SIGTERM (graceful) or SIGKILL (force)
- Confirm or cancel the action

## Filter Dialog

When filtering (`/`):

- Type a filter string to match against process name, command, PID, or username
- Press Enter to apply
- Submit an empty string to clear the filter

## Mouse Support

| Action | Effect |
|--------|--------|
| Click on pane | Focus that pane |
| Click on process row | Select that process |
| Scroll wheel | Scroll the process list |

Disable mouse with `--no-mouse` or set `tui.mouse_enabled: false` in config.

## Customizing Shortcuts

```yaml
tui:
  keybindings:
    quit: q
    help: "?"
    filter: /
    kill_process: k
    refresh: r
    toggle_tree: t
    next_sort: s
```
