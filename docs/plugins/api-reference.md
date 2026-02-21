# Plugin API Reference

## API Version

Current API version: **1.0**

Plugins declare compatibility via the `api_version` class attribute. Major version changes are breaking; minor versions are additive.

## Base Classes

All plugin base classes are in `uptop.plugin_api.base`.

### PluginBase

Common base for all plugin types.

```python
class PluginBase(ABC):
    # Class attributes (set in subclass)
    name: str               # Unique identifier (snake_case)
    display_name: str       # Human-readable name
    version: str            # Semver string (e.g., "0.1.0")
    api_version: str        # Target API version (e.g., "1.0")
    description: str        # Brief description
    author: str             # Plugin author

    # Instance attributes
    config: dict            # Plugin-specific config
    enabled: bool           # Whether plugin is active

    # Methods
    def initialize(self, config=None): ...
    def shutdown(self): ...
    def get_ai_help_docs(self) -> str: ...

    @classmethod
    def get_plugin_type(cls) -> PluginType: ...
    @classmethod
    def get_metadata(cls) -> PluginMetadata: ...
```

### PanePlugin

```python
class PanePlugin(PluginBase):
    default_refresh_interval: float = 1.0

    async def collect_data(self) -> MetricData: ...
    def render_tui(self, data, size=None, mode=None) -> Widget: ...
    def get_schema(self) -> type[BaseModel]: ...
```

### CollectorPlugin

```python
class CollectorPlugin(PluginBase):
    target_pane: str = ""

    def collect(self, context) -> dict[str, Any]: ...
```

### FormatterPlugin

```python
class FormatterPlugin(PluginBase):
    format_name: str = ""
    cli_flag: str = ""
    file_extension: str = ".txt"

    def format(self, data: dict[str, Any]) -> str: ...
```

### ActionPlugin

```python
class ActionPlugin(PluginBase):
    keyboard_shortcut: str = ""
    requires_confirmation: bool = False
    description_short: str = ""

    def can_execute(self, context) -> bool: ...
    async def execute(self, context) -> Any: ...
```

## Data Models

### MetricData

Base class for all pane data models (from `uptop.models.base`):

```python
from uptop.models.base import MetricData, gauge_field, counter_field

class MyData(MetricData):
    value: float = gauge_field("Current value")
    total: int = counter_field("Cumulative count", ge=0)
```

### MetricType

```python
class MetricType(str, Enum):
    COUNTER = "counter"     # Monotonically increasing
    GAUGE = "gauge"         # Can go up or down
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
```

### DisplayMode

```python
class DisplayMode(str, Enum):
    MICRO = "micro"
    MINIMIZED = "minimized"
    MEDIUM = "medium"
    MAXIMIZED = "maximized"
```

### PluginType

```python
class PluginType(str, Enum):
    PANE = "pane"
    COLLECTOR = "collector"
    FORMATTER = "formatter"
    ACTION = "action"
```

## Introspection

```python
from uptop.models.base import get_metric_type

# Returns MetricType.GAUGE
get_metric_type(MyData, "value")

# Returns MetricType.COUNTER
get_metric_type(MyData, "total")
```

## Plugin Validation

Run `uptop --check-plugins` to validate all discovered plugins. Checks include:

- API version compatibility
- Required methods exist and are callable
- `get_schema()` returns a valid Pydantic `BaseModel` subclass (pane plugins)
- Plugin loads without errors

## Entry Point Groups

| Group | Plugin Type |
|-------|-------------|
| `uptop.panes` | PanePlugin |
| `uptop.collectors` | CollectorPlugin |
| `uptop.formatters` | FormatterPlugin |
| `uptop.actions` | ActionPlugin |
