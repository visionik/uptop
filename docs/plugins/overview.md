# Plugin Development Overview

uptop is built on a plugin architecture. The core monitoring panes (CPU, Memory, Processes, Network, Disk) are themselves plugins, validating the same APIs available to external extensions.

## Plugin Types

| Type | Purpose | Base Class |
|------|---------|------------|
| **PanePlugin** | Create new monitoring panes with data collection and TUI rendering | `PanePlugin` |
| **CollectorPlugin** | Contribute additional data to existing panes | `CollectorPlugin` |
| **FormatterPlugin** | Add new output formats for CLI mode | `FormatterPlugin` |
| **ActionPlugin** | Add keyboard-triggered actions in the TUI | `ActionPlugin` |

## Plugin Discovery

Plugins are discovered through two mechanisms:

### 1. Entry Points (Installed Packages)

Register plugins in your package's `pyproject.toml`:

```toml
[project.entry-points."uptop.panes"]
my_pane = "my_package.pane:MyPane"

[project.entry-points."uptop.collectors"]
my_collector = "my_package.collector:MyCollector"

[project.entry-points."uptop.formatters"]
my_formatter = "my_package.formatter:MyFormatter"

[project.entry-points."uptop.actions"]
my_action = "my_package.action:MyAction"
```

### 2. Directory Scanning

Place plugin files in `~/.uptop/plugins/`. Any `.py` file in this directory is scanned for plugin classes.

```
~/.uptop/plugins/
    docker_pane.py
    weather.py
    custom_formatter.py
```

## Plugin Lifecycle

1. **Discovery** -- Plugins found via entry points or directory scanning
2. **Registration** -- Plugin metadata stored in the registry
3. **Initialization** -- `plugin.initialize(config)` called with plugin-specific config
4. **Runtime** -- Plugin methods called as needed (collect, render, format, execute)
5. **Shutdown** -- `plugin.shutdown()` called for cleanup

## API Versioning

Plugins declare their target API version:

```python
class MyPane(PanePlugin):
    api_version = "1.0"
```

- **Major version changes** indicate breaking API changes
- **Minor version changes** are additive only
- Use `uptop --check-plugins` to validate all plugins

## Trust Model

Plugins are trusted code -- there is no sandbox. Installing a plugin is equivalent to trusting its code. Actions that modify system state (like killing processes) should require user confirmation.

## Quick Example

Here's a minimal pane plugin:

```python
from pydantic import BaseModel
from textual.widgets import Static

from uptop.models.base import MetricData
from uptop.plugin_api.base import PanePlugin


class HelloData(MetricData):
    """Data model for hello pane."""
    message: str = "Hello, World!"


class HelloPane(PanePlugin):
    name = "hello"
    display_name = "Hello World"
    version = "0.1.0"
    description = "A minimal example pane plugin"
    default_refresh_interval = 5.0

    async def collect_data(self) -> HelloData:
        return HelloData()

    def render_tui(self, data, size=None, mode=None):
        return Static(data.message)

    def get_schema(self):
        return HelloData
```

See the detailed guides for each plugin type:

- [Creating Panes](creating-panes.md)
- [Creating Collectors](creating-collectors.md)
- [Creating Formatters](creating-formatters.md)
- [Creating Actions](creating-actions.md)
- [API Reference](api-reference.md)
