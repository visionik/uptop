# Themes and Customization

## Built-in Themes

uptop ships with 5 themes. Set via CLI or config:

```bash
uptop --theme nord
```

```yaml
tui:
  theme: nord
```

### Dark (Default)

Dark background with high contrast. Best for most terminal setups.

### Light

Light background suitable for well-lit environments or light terminal themes.

### Solarized

Based on the [Solarized](https://ethanschoonover.com/solarized/) color palette. Works with both Solarized Dark and Light terminal settings.

### Nord

Based on the [Nord](https://www.nordtheme.com/) color palette. Cool, blue-tinted arctic colors.

### Gruvbox

Based on the [Gruvbox](https://github.com/morhetz/gruvbox) color palette. Warm, retro feel.

## Theme Colors

Each theme defines colors for:

- **Primary colors**: background, secondary background, foreground, muted foreground
- **Accent colors**: primary and secondary accent
- **Border colors**: normal and focused state
- **Semantic colors**: success (green), warning (yellow), error (red), info (blue)
- **Table colors**: header, odd/even row backgrounds
- **Widget colors**: scrollbar, progress bars, buttons, inputs

## Display Modes

Each pane supports 4 display density modes, cycled with the `m` key:

| Mode | Use Case |
|------|----------|
| **Micro** | Dashboards with many panes; shows single-line summaries |
| **Minimized** | Compact view with essential metrics only |
| **Medium** | Default balanced view |
| **Maximized** | Full detail including sparklines, graphs, and extended info |

## Layout Presets

Define named layouts in your config:

```yaml
tui:
  layouts:
    default: standard
    custom_layouts:
      server_focus:
        - [cpu, memory]
        - [network, disk]
      dev_focus:
        - [cpu, processes]
        - [memory, disk]
      minimal:
        - [cpu, memory]
```

## Keybinding Customization

Override default keybindings in your config:

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

## Unit Preferences

Customize how values are displayed:

```yaml
display:
  units:
    memory: binary         # KiB, MiB, GiB (1024-based)
    # memory: decimal      # KB, MB, GB (1000-based)
    network: decimal       # KB/s, MB/s
    temperature: celsius   # or "fahrenheit"
  decimal_places: 1
  show_percentages: true
```
