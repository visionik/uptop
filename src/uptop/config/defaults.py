"""Default configuration values for uptop.

This module defines the default configuration used when no config file exists
or when config values are not specified. All configuration options are documented
here for reference.

Environment Variables:
    UPTOP_CONFIG_PATH: Override default config file path
    Any config value can reference environment variables using ${VAR} syntax

Config File Locations (in order of precedence):
    1. Path specified via --config CLI flag
    2. Path specified via UPTOP_CONFIG_PATH environment variable
    3. ~/.config/uptop/config.yaml (XDG default)
    4. ~/.uptop/config.yaml (legacy location)
"""

from typing import Any

# Default configuration dictionary
# This matches the schema defined in SPECIFICATION.md section 4.1
DEFAULT_CONFIG: dict[str, Any] = {
    # Core settings
    "default_mode": "tui",  # "tui" or "cli" - default mode when running uptop
    "interval": 1.0,  # Default refresh interval in seconds
    # TUI settings
    "tui": {
        "theme": "dark",  # Theme name: dark, light, solarized, nord, gruvbox, custom
        "mouse_enabled": True,  # Enable mouse support in TUI
        # Pane configuration - each pane can have individual settings
        "panes": {
            "cpu": {
                "enabled": True,
                "refresh_interval": 1.0,  # Override global interval for this pane
                "position": [0, 0],  # Grid position [column, row]
                "size": [2, 1],  # Grid size [width, height]
            },
            "memory": {
                "enabled": True,
                "refresh_interval": 2.0,
                "position": [0, 1],
                "size": [1, 1],
            },
            "processes": {
                "enabled": True,
                "refresh_interval": 2.0,
                "position": [2, 0],
                "size": [2, 2],
                "default_sort": "cpu_percent",  # Sort column
                "default_filter": None,  # Filter expression
            },
            "network": {
                "enabled": True,
                "refresh_interval": 1.0,
            },
            "disk": {
                "enabled": True,
                "refresh_interval": 5.0,
            },
            "gpu": {
                "enabled": "auto",  # "auto" to auto-detect GPU availability
                "refresh_interval": 1.0,
            },
            "sensors": {
                "enabled": True,
                "refresh_interval": 3.0,
            },
        },
        # Layout presets for quick switching
        "layouts": {
            "default": "standard",
            "custom_layouts": {
                "server_focus": [["cpu", "memory"], ["network", "disk"]],
                "dev_focus": [["cpu", "processes"], ["memory", "disk"]],
            },
        },
        # Keyboard shortcuts (fully configurable)
        "keybindings": {
            "quit": "q",
            "help": "?",
            "filter": "/",
            "kill_process": "k",
            "change_priority": "n",
            "refresh": "r",
            "toggle_tree": "t",
            "next_sort": "s",
        },
    },
    # CLI settings
    "cli": {
        "default_format": "json",  # Output format: json, markdown, prometheus
        "default_output_mode": "once",  # Output mode: once, stream, continuous
        "pretty_print": True,  # Pretty-print JSON output
    },
    # Display preferences
    "display": {
        "units": {
            "memory": "binary",  # "binary" (KiB/MiB) or "decimal" (KB/MB)
            "network": "decimal",  # "binary" or "decimal"
            "temperature": "celsius",  # "celsius" or "fahrenheit"
        },
        "decimal_places": 1,  # Number of decimal places for numeric values
        "show_percentages": True,  # Show percentage values where applicable
    },
    # Plugin settings
    "plugins": {
        "directory": "~/.uptop/plugins",  # Custom plugin directory
        "auto_load": True,  # Auto-load discovered plugins
        "enabled_plugins": [],  # List of explicitly enabled plugins
        "plugin_config": {},  # Plugin-specific configuration
    },
    # Process filter presets
    "process_filters": {
        "high_cpu": "cpu_percent > 50",
        "high_mem": "memory_mb > 100",
        "my_user": "username == '${USER}'",
    },
    # Logging configuration (for debugging)
    "logging": {
        "enabled": False,
        "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
        "file": "~/.uptop/uptop.log",
    },
}
