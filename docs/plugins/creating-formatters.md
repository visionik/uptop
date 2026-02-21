# Creating Formatter Plugins

Formatter plugins add new output formats for CLI mode. The built-in formatters are JSON, Markdown, and Prometheus.

## Base Class

```python
from uptop.plugin_api.base import FormatterPlugin

class XMLFormatter(FormatterPlugin):
    name = "xml_formatter"
    display_name = "XML Formatter"
    version = "0.1.0"
    format_name = "xml"          # Used in --format selection
    cli_flag = "--xml"           # CLI flag to activate
    file_extension = ".xml"      # Default output file extension

    def format(self, data):
        """Format system data as a string.

        Args:
            data: Dictionary containing system metrics snapshot

        Returns:
            Formatted string representation
        """
        # Convert data dict to XML string
        return dict_to_xml(data)
```

## Data Structure

The `data` parameter passed to `format()` is a dictionary with this structure:

```python
{
    "timestamp": "2026-02-20T10:30:00Z",
    "panes": {
        "cpu": { ... },      # CPUData model as dict
        "memory": { ... },   # MemoryData model as dict
        "processes": { ... },
        "network": { ... },
        "disk": { ... },
    }
}
```

## Registration

```toml
[project.entry-points."uptop.formatters"]
xml = "my_package:XMLFormatter"
```
