# Creating Pane Plugins

Pane plugins are the most common type. Each pane collects data and renders it as a TUI widget.

## Required Methods

A `PanePlugin` subclass must implement:

| Method | Description |
|--------|-------------|
| `collect_data()` | Async method that gathers metrics and returns a `MetricData` subclass |
| `render_tui(data, size, mode)` | Returns a Textual `Widget` for the TUI display |
| `get_schema()` | Returns the Pydantic model class used by `collect_data()` |

## Step-by-Step Example

### 1. Define Your Data Model

Use Pydantic models extending `MetricData` for type safety and automatic JSON schema generation:

```python
from pydantic import Field
from uptop.models.base import MetricData, gauge_field

class WeatherData(MetricData):
    """Weather monitoring data."""
    temperature: float = gauge_field("Temperature in Celsius")
    humidity: float = gauge_field("Humidity percentage", ge=0, le=100)
    location: str = Field(default="Unknown", description="Location name")
```

Use `gauge_field()` and `counter_field()` helpers from `uptop.models.base` to annotate metric types. This enables proper Prometheus TYPE annotations in CLI output.

### 2. Implement the Plugin Class

```python
from uptop.plugin_api.base import PanePlugin
from uptop.models.base import DisplayMode

class WeatherPane(PanePlugin):
    name = "weather"
    display_name = "Weather"
    version = "0.1.0"
    api_version = "1.0"
    description = "Display current weather conditions"
    default_refresh_interval = 300.0  # 5 minutes

    async def collect_data(self) -> WeatherData:
        # Use async HTTP to fetch weather data
        # For real implementations, use httpx or aiohttp
        return WeatherData(
            temperature=22.5,
            humidity=65.0,
            location="San Francisco",
        )

    def render_tui(self, data, size=None, mode=None):
        from textual.widgets import Static

        if mode == DisplayMode.MICRO:
            return Static(f"{data.temperature:.0f}C")
        elif mode == DisplayMode.MINIMIZED:
            return Static(f"{data.location}: {data.temperature:.1f}C")
        else:
            return Static(
                f"Location: {data.location}\n"
                f"Temperature: {data.temperature:.1f}C\n"
                f"Humidity: {data.humidity:.0f}%"
            )

    def get_schema(self):
        return WeatherData
```

### 3. Handle Display Modes

The `render_tui` method receives an optional `mode` parameter (`DisplayMode` enum) indicating the display density:

- `MICRO` -- Ultra-compact, single line
- `MINIMIZED` -- Essential info only
- `MEDIUM` -- Balanced (default)
- `MAXIMIZED` -- Full detail

Adapt your widget's output based on the mode for the best user experience.

### 4. Register the Plugin

**Option A: Entry point** (for installable packages):

```toml
[project.entry-points."uptop.panes"]
weather = "my_weather_plugin.pane:WeatherPane"
```

**Option B: Plugin directory** (for local plugins):

Save as `~/.uptop/plugins/weather.py`.

## Configuration

Plugins receive configuration via `initialize()`:

```python
def initialize(self, config=None):
    super().initialize(config)
    self.api_key = self.config.get("api_key", "")
    self.location = self.config.get("location", "auto")
```

Users configure plugins in `config.yaml`:

```yaml
plugins:
  plugin_config:
    weather:
      api_key: "${WEATHER_API_KEY}"
      location: "San Francisco"
```

## Error Handling

- `collect_data()` exceptions are caught by the scheduler -- the pane shows an error state while others keep running
- Return stale data rather than raising if partial data is available
- Use logging for debug information: `import logging; logger = logging.getLogger(__name__)`

## Testing

```python
import pytest
from my_plugin import WeatherPane, WeatherData

@pytest.fixture
def pane():
    p = WeatherPane()
    p.initialize()
    return p

@pytest.mark.asyncio
async def test_collect_data(pane):
    data = await pane.collect_data()
    assert isinstance(data, WeatherData)
    assert data.temperature is not None

def test_render_tui(pane):
    data = WeatherData(temperature=22.5, humidity=65.0)
    widget = pane.render_tui(data)
    assert widget is not None

def test_schema(pane):
    schema = pane.get_schema()
    assert schema is WeatherData
```
