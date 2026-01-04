"""Configuration module for uptop.

This module provides:
- Pydantic models for configuration validation
- YAML config file loading and discovery
- Default configuration values
- Environment variable expansion
- Clear error messages for config issues
"""

from uptop.config.defaults import DEFAULT_CONFIG
from uptop.config.loader import (
    CLIConfig,
    Config,
    ConfigError,
    ConfigKeyError,
    ConfigSyntaxError,
    ConfigValidationError,
    DisplayConfig,
    LoggingConfig,
    PaneConfig,
    PluginsConfig,
    TUIConfig,
    UnitsConfig,
    get_config_path,
    load_config,
)

__all__ = [
    "Config",
    "CLIConfig",
    "ConfigError",
    "ConfigKeyError",
    "ConfigSyntaxError",
    "ConfigValidationError",
    "DisplayConfig",
    "LoggingConfig",
    "PaneConfig",
    "PluginsConfig",
    "TUIConfig",
    "UnitsConfig",
    "DEFAULT_CONFIG",
    "get_config_path",
    "load_config",
]
