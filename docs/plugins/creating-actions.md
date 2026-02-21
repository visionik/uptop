# Creating Action Plugins

Action plugins provide keyboard-triggered operations in the TUI.

## Base Class

```python
from uptop.plugin_api.base import ActionPlugin

class ReniceProcAction(ActionPlugin):
    name = "renice_process"
    display_name = "Renice Process"
    version = "0.1.0"
    keyboard_shortcut = "n"
    requires_confirmation = True
    description_short = "Change process priority"

    def can_execute(self, context):
        """Check if this action is available.

        Args:
            context: Current UI context (selected pane, process, etc.)

        Returns:
            True if a process is selected
        """
        return getattr(context, "selected_process", None) is not None

    async def execute(self, context):
        """Execute the action.

        Args:
            context: Current UI context

        Returns:
            Result of the action
        """
        pid = context.selected_process.pid
        # Perform renice operation
        ...
```

## Key Attributes

| Attribute | Description |
|-----------|-------------|
| `keyboard_shortcut` | Key to trigger this action (e.g., `"n"`, `"ctrl+r"`) |
| `requires_confirmation` | If `True`, the TUI shows a confirmation dialog before executing |
| `description_short` | Brief text shown in the keybinding footer |

## Registration

```toml
[project.entry-points."uptop.actions"]
renice = "my_package:ReniceProcAction"
```
