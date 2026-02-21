# Creating Collector Plugins

Collector plugins contribute additional data to existing panes without creating a new pane. For example, adding Docker container info to the process pane.

## Base Class

```python
from uptop.plugin_api.base import CollectorPlugin

class MyCollector(CollectorPlugin):
    name = "my_collector"
    display_name = "My Collector"
    version = "0.1.0"
    target_pane = "process"  # Which pane to contribute data to

    def collect(self, context):
        """Return additional fields to merge into pane data.

        Args:
            context: Context object from the target pane

        Returns:
            Dictionary of additional fields
        """
        return {"custom_field": "value"}
```

## Example: Docker Process Info

```python
class DockerProcessInfo(CollectorPlugin):
    name = "docker_process"
    display_name = "Docker Process Info"
    version = "0.1.0"
    target_pane = "process"
    description = "Adds Docker container ID to process data"

    def collect(self, context):
        pid = getattr(context, "pid", None)
        if pid:
            container_id = self._get_container_id(pid)
            return {"container_id": container_id}
        return {}

    def _get_container_id(self, pid):
        # Implementation to resolve PID to container
        ...
```

## Registration

```toml
[project.entry-points."uptop.collectors"]
docker_process = "my_package:DockerProcessInfo"
```

Or place in `~/.uptop/plugins/`.
