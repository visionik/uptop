"""Configuration loading and validation for uptop.

This module provides:
- Pydantic models for configuration validation
- YAML config file discovery and loading
- Environment variable expansion in config values
- Merging of config file with defaults
- Clear, user-friendly error messages for config issues
"""

from difflib import get_close_matches
import os
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
import yaml

from uptop.config.defaults import DEFAULT_CONFIG


class ConfigError(Exception):
    """Base exception for configuration errors.

    Provides user-friendly error messages with context about what went wrong
    and suggestions for how to fix it.

    Attributes:
        message: The main error message
        file_path: Path to the config file (if applicable)
        line_number: Line number where the error occurred (if known)
        suggestion: Helpful suggestion for fixing the error
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        column: int | None = None,
        suggestion: str | None = None,
        context_lines: list[str] | None = None,
    ) -> None:
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        self.column = column
        self.suggestion = suggestion
        self.context_lines = context_lines
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with context and suggestions."""
        parts = []

        # Header with location info
        if self.file_path:
            location = f"Error in {self.file_path}"
            if self.line_number:
                location += f" line {self.line_number}"
            parts.append(location + ":")
        else:
            parts.append("Configuration error:")

        # Main message
        parts.append(f"  {self.message}")

        # Context lines with pointer
        if self.context_lines and self.column:
            parts.append("")
            for line in self.context_lines:
                parts.append(f"    {line}")
            # Add pointer
            pointer = " " * (self.column + 3) + "^" * max(1, len(str(self.column)))
            parts.append(pointer)

        # Suggestion
        if self.suggestion:
            parts.append("")
            parts.append(f"  Suggestion: {self.suggestion}")

        return "\n".join(parts)


class ConfigSyntaxError(ConfigError):
    """Error for YAML syntax issues."""

    pass


class ConfigValidationError(ConfigError):
    """Error for configuration value validation failures."""

    pass


class ConfigKeyError(ConfigError):
    """Error for unknown or invalid configuration keys."""

    pass


# Known valid configuration keys at each level for suggestions
VALID_TOP_LEVEL_KEYS = {
    "default_mode",
    "interval",
    "tui",
    "cli",
    "display",
    "plugins",
    "process_filters",
    "logging",
}

VALID_TUI_KEYS = {
    "theme",
    "mouse_enabled",
    "panes",
    "layouts",
    "keybindings",
}

VALID_PANE_KEYS = {
    "enabled",
    "refresh_interval",
    "position",
    "size",
}

VALID_CLI_KEYS = {
    "default_format",
    "default_output_mode",
    "pretty_print",
}

VALID_DISPLAY_KEYS = {
    "units",
    "decimal_places",
    "show_percentages",
}

VALID_LOGGING_KEYS = {
    "enabled",
    "level",
    "file",
}

# Environment variable pattern: ${VAR} or ${VAR:-default}
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _suggest_key(unknown_key: str, valid_keys: set[str]) -> str | None:
    """Suggest a similar valid key for an unknown key.

    Args:
        unknown_key: The key that was not recognized
        valid_keys: Set of valid key names

    Returns:
        A suggestion message, or None if no good match found
    """
    matches = get_close_matches(unknown_key, list(valid_keys), n=1, cutoff=0.6)
    if matches:
        return f"Did you mean '{matches[0]}'?"
    return None


def _get_type_description(value: Any) -> str:
    """Get a human-readable type description for a value.

    Args:
        value: The value to describe

    Returns:
        Human-readable type description
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return f'string "{value}"'
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _format_pydantic_error(
    error: ValidationError,
    config_data: dict[str, Any],
    file_path: str | None = None,
) -> ConfigValidationError:
    """Convert a Pydantic ValidationError to a user-friendly ConfigValidationError.

    Args:
        error: The Pydantic validation error
        config_data: The original config data for context
        file_path: Path to the config file

    Returns:
        A ConfigValidationError with helpful message and suggestions
    """
    # Get the first error for detailed reporting
    errors = error.errors()
    if not errors:
        return ConfigValidationError(
            "Configuration validation failed",
            file_path=file_path,
        )

    first_error = errors[0]
    loc = first_error.get("loc", ())
    msg = first_error.get("msg", "Invalid value")
    error_type = first_error.get("type", "")
    ctx = first_error.get("ctx", {})

    # Build the path to the problematic key
    path = ".".join(str(part) for part in loc)

    # Get the actual value that caused the error
    actual_value = config_data
    for key in loc:
        if isinstance(actual_value, dict):
            actual_value = actual_value.get(key)
        elif isinstance(actual_value, list) and isinstance(key, int):
            actual_value = actual_value[key] if key < len(actual_value) else None
        else:
            break

    # Build a helpful message based on error type
    suggestion = None

    if error_type == "literal_error":
        # Wrong value for a literal field (e.g., mode, format)
        expected = ctx.get("expected", "")
        message = f"Invalid value for '{path}': got {_get_type_description(actual_value)}"
        suggestion = f"Expected one of: {expected}"

    elif error_type == "greater_than_equal" or error_type == "less_than_equal":
        # Value out of range
        limit = ctx.get("ge") or ctx.get("le") or ctx.get("limit_value")
        message = f"Value for '{path}' is out of range: {actual_value}"
        if error_type == "greater_than_equal":
            suggestion = f"Value must be at least {limit}"
        else:
            suggestion = f"Value must be at most {limit}"

    elif error_type == "int_parsing" or error_type == "float_parsing":
        # Type conversion error
        message = f"Invalid number for '{path}': got {_get_type_description(actual_value)}"
        suggestion = "Please provide a valid number"

    elif error_type == "string_type":
        message = f"Expected string for '{path}': got {_get_type_description(actual_value)}"
        suggestion = "Please provide a text value"

    elif error_type == "bool_type" or error_type == "bool_parsing":
        message = f"Expected boolean for '{path}': got {_get_type_description(actual_value)}"
        suggestion = "Use 'true' or 'false'"

    elif error_type == "list_type":
        message = f"Expected list for '{path}': got {_get_type_description(actual_value)}"
        suggestion = "Please provide a list (e.g., [1, 2])"

    elif "extra_forbidden" in error_type:
        # Unknown key in a strict section
        unknown_key = str(loc[-1]) if loc else "unknown"
        message = f"Unknown configuration key '{path}'"
        # Try to suggest a valid alternative
        parent_path = loc[:-1] if len(loc) > 1 else ()
        if not parent_path:
            suggestion = _suggest_key(unknown_key, VALID_TOP_LEVEL_KEYS)
        elif parent_path == ("tui",):
            suggestion = _suggest_key(unknown_key, VALID_TUI_KEYS)
        elif parent_path == ("cli",):
            suggestion = _suggest_key(unknown_key, VALID_CLI_KEYS)
        elif parent_path == ("display",):
            suggestion = _suggest_key(unknown_key, VALID_DISPLAY_KEYS)
        elif parent_path == ("logging",):
            suggestion = _suggest_key(unknown_key, VALID_LOGGING_KEYS)

        if not suggestion:
            suggestion = "Check the documentation for valid configuration options"

    else:
        # Generic error message
        message = f"Invalid value for '{path}': {msg}"

    return ConfigValidationError(
        message,
        file_path=file_path,
        suggestion=suggestion,
    )


def _format_yaml_error(
    error: yaml.YAMLError,
    file_path: str | None = None,
    content: str | None = None,
) -> ConfigSyntaxError:
    """Convert a YAML error to a user-friendly ConfigSyntaxError.

    Args:
        error: The YAML error
        file_path: Path to the config file
        content: The file content for context

    Returns:
        A ConfigSyntaxError with helpful message and context
    """
    line_number = None
    column = None
    context_lines = None
    suggestion = None

    # Extract position information if available
    if hasattr(error, "problem_mark") and error.problem_mark:
        mark = error.problem_mark
        line_number = mark.line + 1  # YAML uses 0-indexed lines
        column = mark.column + 1

        # Get context lines from content
        if content:
            lines = content.splitlines()
            if 0 <= mark.line < len(lines):
                context_lines = [lines[mark.line]]

    # Analyze the error message for helpful suggestions
    error_str = str(error).lower()

    if "could not find expected ':'" in error_str:
        suggestion = "Check for missing colons after keys (e.g., 'key: value')"
    elif "found character" in error_str and "tab" in error_str:
        suggestion = "Use spaces instead of tabs for indentation"
    elif "mapping values are not allowed" in error_str:
        suggestion = "Check your indentation - make sure nested keys are properly indented"
    elif "expected '<document start>'" in error_str:
        suggestion = "Check for invalid characters at the start of the file"
    elif "found undefined alias" in error_str:
        suggestion = "Check that all YAML anchors (&name) are defined before aliases (*name)"
    elif "duplicate key" in error_str:
        suggestion = "Remove the duplicate key - each key can only appear once"

    message = "Invalid YAML syntax"
    if hasattr(error, "problem") and error.problem:
        message = f"YAML syntax error: {error.problem}"

    return ConfigSyntaxError(
        message,
        file_path=file_path,
        line_number=line_number,
        column=column,
        context_lines=context_lines,
        suggestion=suggestion,
    )


def expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in config values.

    Supports ${VAR} and ${VAR:-default} syntax.

    Args:
        value: The value to expand (string, dict, list, or other)

    Returns:
        The value with environment variables expanded
    """
    if isinstance(value, str):

        def replace_env_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default_value = match.group(2)
            env_value = os.environ.get(var_name)
            if env_value is not None:
                return env_value
            if default_value is not None:
                return default_value
            return match.group(0)  # Keep original if not found and no default

        return ENV_VAR_PATTERN.sub(replace_env_var, value)
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary with defaults
        override: Dictionary with overriding values

    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Pydantic Configuration Models


class PaneConfig(BaseModel):
    """Configuration for an individual pane."""

    model_config = ConfigDict(extra="allow")

    enabled: bool | Literal["auto"] = True
    refresh_interval: float = Field(default=1.0, ge=0.1, le=3600)
    position: list[int] | None = None
    size: list[int] | None = None

    @field_validator("position", "size", mode="before")
    @classmethod
    def validate_coordinates(cls, v: list[int] | None) -> list[int] | None:
        """Validate position and size are 2-element lists."""
        if v is not None:
            if len(v) != 2:
                raise ValueError("Must be a 2-element list [x, y]")
            if any(coord < 0 for coord in v):
                raise ValueError("Coordinates must be non-negative")
        return v


class LayoutsConfig(BaseModel):
    """Configuration for layout presets."""

    model_config = ConfigDict(extra="allow")

    default: str = "standard"
    custom_layouts: dict[str, list[list[str]]] = Field(default_factory=dict)


class KeybindingsConfig(BaseModel):
    """Keyboard shortcut configuration."""

    model_config = ConfigDict(extra="allow")

    quit: str = "q"
    help: str = "?"
    filter: str = "/"
    kill_process: str = "k"
    change_priority: str = "n"
    refresh: str = "r"
    toggle_tree: str = "t"
    next_sort: str = "s"


class TUIConfig(BaseModel):
    """TUI-specific configuration."""

    model_config = ConfigDict(extra="allow")

    theme: str = "dark"
    mouse_enabled: bool = True
    panes: dict[str, PaneConfig] = Field(default_factory=dict)
    layouts: LayoutsConfig = Field(default_factory=LayoutsConfig)
    keybindings: KeybindingsConfig = Field(default_factory=KeybindingsConfig)

    @field_validator("panes", mode="before")
    @classmethod
    def validate_panes(cls, v: dict[str, Any]) -> dict[str, PaneConfig]:
        """Convert raw pane dicts to PaneConfig objects."""
        if isinstance(v, dict):
            return {
                name: PaneConfig(**config) if isinstance(config, dict) else config
                for name, config in v.items()
            }
        return v


class CLIConfig(BaseModel):
    """CLI-specific configuration."""

    model_config = ConfigDict(extra="forbid")

    default_format: Literal["json", "markdown", "prometheus"] = "json"
    default_output_mode: Literal["once", "stream", "continuous"] = "once"
    pretty_print: bool = True


class UnitsConfig(BaseModel):
    """Unit display configuration."""

    model_config = ConfigDict(extra="forbid")

    memory: Literal["binary", "decimal"] = "binary"
    network: Literal["binary", "decimal"] = "decimal"
    temperature: Literal["celsius", "fahrenheit"] = "celsius"


class DisplayConfig(BaseModel):
    """Display preferences configuration."""

    model_config = ConfigDict(extra="forbid")

    units: UnitsConfig = Field(default_factory=UnitsConfig)
    decimal_places: int = Field(default=1, ge=0, le=10)
    show_percentages: bool = True


class PluginsConfig(BaseModel):
    """Plugin configuration."""

    model_config = ConfigDict(extra="allow")

    directory: str = "~/.uptop/plugins"
    auto_load: bool = True
    enabled_plugins: list[str] = Field(default_factory=list)
    plugin_config: dict[str, dict[str, Any]] = Field(default_factory=dict)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str = "~/.uptop/uptop.log"


class Config(BaseModel):
    """Main configuration model for uptop.

    This model validates and holds all configuration for the application.
    Configuration is loaded from YAML files and can be overridden by CLI flags.
    """

    model_config = ConfigDict(extra="allow")

    # Core settings
    default_mode: Literal["tui", "cli"] = "tui"
    interval: float = Field(default=1.0, ge=0.1, le=3600)
    interval_override: bool = Field(default=False, exclude=True)  # Track CLI override

    # Section configs
    tui: TUIConfig = Field(default_factory=TUIConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    process_filters: dict[str, str] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def get_pane_config(self, pane_name: str) -> PaneConfig:
        """Get configuration for a specific pane.

        Args:
            pane_name: Name of the pane

        Returns:
            PaneConfig for the pane (default if not configured)
        """
        return self.tui.panes.get(pane_name, PaneConfig())

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """Get configuration for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin configuration dict (empty if not configured)
        """
        return self.plugins.plugin_config.get(plugin_name, {})


def get_config_path(custom_path: str | None = None) -> Path | None:
    """Determine the configuration file path.

    Checks locations in this order:
    1. Custom path (if provided via --config flag)
    2. UPTOP_CONFIG_PATH environment variable
    3. ~/.config/uptop/config.yaml (XDG standard)
    4. ~/.uptop/config.yaml (legacy location)

    Args:
        custom_path: Optional custom config path from CLI

    Returns:
        Path to config file if found, None otherwise
    """
    # Check custom path first
    if custom_path:
        path = Path(custom_path).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Config file not found: {custom_path}")

    # Check environment variable
    env_path = os.environ.get("UPTOP_CONFIG_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return path
        # Env var set but file not found - warn but continue
        return None

    # Check XDG standard location
    xdg_path = Path.home() / ".config" / "uptop" / "config.yaml"
    if xdg_path.exists():
        return xdg_path

    # Check legacy location
    legacy_path = Path.home() / ".uptop" / "config.yaml"
    if legacy_path.exists():
        return legacy_path

    # No config file found
    return None


def load_config(
    config_path: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
    raise_on_error: bool = True,
) -> Config:
    """Load and validate configuration.

    Configuration is merged in this order (later overrides earlier):
    1. Default configuration
    2. Config file (if found)
    3. CLI overrides (if provided)

    Environment variables in config values are expanded using ${VAR} syntax.

    Args:
        config_path: Optional custom config file path
        cli_overrides: Optional dict of CLI argument overrides
        raise_on_error: If True, raise ConfigError on issues; if False, return
            defaults with warnings logged

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If custom config path doesn't exist
        ConfigSyntaxError: If config file has invalid YAML syntax
        ConfigValidationError: If config values are invalid
    """
    # Start with defaults
    config_data = DEFAULT_CONFIG.copy()
    resolved_path: Path | str | None = None
    file_content: str | None = None

    # Try to load config file
    try:
        path = get_config_path(config_path)
        if path:
            resolved_path = path
            with open(path) as f:
                file_content = f.read()
            try:
                file_config = yaml.safe_load(file_content) or {}
            except yaml.YAMLError as e:
                if raise_on_error:
                    raise _format_yaml_error(e, str(path), file_content) from e
                # On error with raise_on_error=False, use defaults
                file_config = {}

            config_data = deep_merge(config_data, file_config)

    except FileNotFoundError:
        # Re-raise file not found errors as-is
        raise

    # Apply CLI overrides
    interval_was_overridden = False
    if cli_overrides:
        if "interval" in cli_overrides:
            interval_was_overridden = True
        config_data = deep_merge(config_data, cli_overrides)

    # Expand environment variables
    config_data = expand_env_vars(config_data)

    # Validate and return Config object
    try:
        config = Config(**config_data)
    except ValidationError as e:
        if raise_on_error:
            raise _format_pydantic_error(
                e,
                config_data,
                str(resolved_path) if resolved_path else None,
            ) from e
        # On error with raise_on_error=False, use defaults
        config = Config(**DEFAULT_CONFIG)

    if interval_was_overridden:
        config.interval_override = True
    return config
