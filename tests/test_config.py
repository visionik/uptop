"""Tests for uptop configuration system."""

import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from pydantic import ValidationError
import pytest
import yaml

from uptop.config import (
    DEFAULT_CONFIG,
    CLIConfig,
    Config,
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
from uptop.config.loader import deep_merge, expand_env_vars


class TestExpandEnvVars:
    """Tests for environment variable expansion."""

    def test_expand_simple_var(self) -> None:
        """Test expanding a simple environment variable."""
        with patch.dict(os.environ, {"TEST_VAR": "hello"}):
            result = expand_env_vars("${TEST_VAR}")
            assert result == "hello"

    def test_expand_var_in_string(self) -> None:
        """Test expanding env var within a string."""
        with patch.dict(os.environ, {"USER": "testuser"}):
            result = expand_env_vars("Hello ${USER}!")
            assert result == "Hello testuser!"

    def test_expand_multiple_vars(self) -> None:
        """Test expanding multiple env vars."""
        with patch.dict(os.environ, {"FOO": "foo", "BAR": "bar"}):
            result = expand_env_vars("${FOO}-${BAR}")
            assert result == "foo-bar"

    def test_expand_with_default(self) -> None:
        """Test ${VAR:-default} syntax."""
        # Unset the variable to test default
        env = os.environ.copy()
        env.pop("UNSET_VAR", None)
        with patch.dict(os.environ, env, clear=True):
            result = expand_env_vars("${UNSET_VAR:-default_value}")
            assert result == "default_value"

    def test_expand_var_overrides_default(self) -> None:
        """Test that set variable overrides default."""
        with patch.dict(os.environ, {"SET_VAR": "actual"}):
            result = expand_env_vars("${SET_VAR:-default}")
            assert result == "actual"

    def test_expand_unset_var_no_default(self) -> None:
        """Test unset variable without default is kept as-is."""
        env = os.environ.copy()
        env.pop("REALLY_UNSET", None)
        with patch.dict(os.environ, env, clear=True):
            result = expand_env_vars("${REALLY_UNSET}")
            assert result == "${REALLY_UNSET}"

    def test_expand_dict(self) -> None:
        """Test expanding env vars in dict values."""
        with patch.dict(os.environ, {"API_KEY": "secret123"}):
            result = expand_env_vars({"key": "${API_KEY}", "other": "static"})
            assert result == {"key": "secret123", "other": "static"}

    def test_expand_list(self) -> None:
        """Test expanding env vars in list items."""
        with patch.dict(os.environ, {"VAR": "value"}):
            result = expand_env_vars(["${VAR}", "static", "${VAR}2"])
            assert result == ["value", "static", "value2"]

    def test_expand_nested(self) -> None:
        """Test expanding env vars in nested structures."""
        with patch.dict(os.environ, {"HOST": "localhost", "PORT": "8080"}):
            config = {
                "server": {
                    "host": "${HOST}",
                    "port": "${PORT}",
                    "endpoints": ["${HOST}/api", "${HOST}/health"],
                }
            }
            result = expand_env_vars(config)
            assert result == {
                "server": {
                    "host": "localhost",
                    "port": "8080",
                    "endpoints": ["localhost/api", "localhost/health"],
                }
            }

    def test_expand_non_string(self) -> None:
        """Test that non-string values are returned unchanged."""
        assert expand_env_vars(42) == 42
        assert expand_env_vars(3.14) == 3.14
        assert expand_env_vars(True) is True
        assert expand_env_vars(None) is None


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_simple_merge(self) -> None:
        """Test simple dict merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        """Test nested dict merge."""
        base = {"a": {"x": 1, "y": 2}, "b": 1}
        override = {"a": {"y": 3, "z": 4}}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}, "b": 1}

    def test_override_replaces_non_dict(self) -> None:
        """Test that override replaces non-dict with dict."""
        base = {"a": "string"}
        override = {"a": {"nested": "value"}}
        result = deep_merge(base, override)
        assert result == {"a": {"nested": "value"}}

    def test_base_unchanged(self) -> None:
        """Test that base dict is not modified."""
        base = {"a": 1}
        override = {"b": 2}
        deep_merge(base, override)
        assert base == {"a": 1}


class TestPaneConfig:
    """Tests for PaneConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = PaneConfig()
        assert config.enabled is True
        assert config.refresh_interval == 1.0
        assert config.position is None
        assert config.size is None

    def test_custom_values(self) -> None:
        """Test custom values."""
        config = PaneConfig(
            enabled=False,
            refresh_interval=2.5,
            position=[1, 2],
            size=[3, 4],
        )
        assert config.enabled is False
        assert config.refresh_interval == 2.5
        assert config.position == [1, 2]
        assert config.size == [3, 4]

    def test_enabled_auto(self) -> None:
        """Test enabled='auto' is valid."""
        config = PaneConfig(enabled="auto")
        assert config.enabled == "auto"

    def test_invalid_position_length(self) -> None:
        """Test position must be 2-element list."""
        with pytest.raises(ValidationError):
            PaneConfig(position=[1])

    def test_invalid_position_negative(self) -> None:
        """Test position must be non-negative."""
        with pytest.raises(ValidationError):
            PaneConfig(position=[-1, 0])

    def test_invalid_refresh_interval(self) -> None:
        """Test refresh_interval bounds."""
        with pytest.raises(ValidationError):
            PaneConfig(refresh_interval=0.05)  # Too small

        with pytest.raises(ValidationError):
            PaneConfig(refresh_interval=4000)  # Too large


class TestTUIConfig:
    """Tests for TUIConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = TUIConfig()
        assert config.theme == "dark"
        assert config.mouse_enabled is True
        assert config.panes == {}

    def test_panes_conversion(self) -> None:
        """Test that pane dicts are converted to PaneConfig."""
        config = TUIConfig(
            panes={
                "cpu": {"enabled": True, "refresh_interval": 1.0},
                "memory": {"enabled": False},
            }
        )
        assert isinstance(config.panes["cpu"], PaneConfig)
        assert config.panes["cpu"].enabled is True
        assert config.panes["memory"].enabled is False


class TestCLIConfig:
    """Tests for CLIConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = CLIConfig()
        assert config.default_format == "json"
        assert config.default_output_mode == "once"
        assert config.pretty_print is True

    def test_valid_formats(self) -> None:
        """Test valid format values."""
        for fmt in ["json", "markdown", "prometheus"]:
            config = CLIConfig(default_format=fmt)
            assert config.default_format == fmt

    def test_invalid_format(self) -> None:
        """Test invalid format raises error."""
        with pytest.raises(ValidationError):
            CLIConfig(default_format="invalid")

    def test_valid_output_modes(self) -> None:
        """Test valid output mode values."""
        for mode in ["once", "stream", "continuous"]:
            config = CLIConfig(default_output_mode=mode)
            assert config.default_output_mode == mode


class TestUnitsConfig:
    """Tests for UnitsConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = UnitsConfig()
        assert config.memory == "binary"
        assert config.network == "decimal"
        assert config.temperature == "celsius"

    def test_valid_values(self) -> None:
        """Test valid unit values."""
        config = UnitsConfig(
            memory="decimal",
            network="binary",
            temperature="fahrenheit",
        )
        assert config.memory == "decimal"
        assert config.network == "binary"
        assert config.temperature == "fahrenheit"


class TestDisplayConfig:
    """Tests for DisplayConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = DisplayConfig()
        assert config.decimal_places == 1
        assert config.show_percentages is True
        assert isinstance(config.units, UnitsConfig)

    def test_decimal_places_bounds(self) -> None:
        """Test decimal_places validation."""
        with pytest.raises(ValidationError):
            DisplayConfig(decimal_places=-1)

        with pytest.raises(ValidationError):
            DisplayConfig(decimal_places=11)


class TestPluginsConfig:
    """Tests for PluginsConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = PluginsConfig()
        assert config.directory == "~/.uptop/plugins"
        assert config.auto_load is True
        assert config.enabled_plugins == []
        assert config.plugin_config == {}


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = LoggingConfig()
        assert config.enabled is False
        assert config.level == "INFO"
        assert config.file == "~/.uptop/uptop.log"

    def test_valid_levels(self) -> None:
        """Test valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = LoggingConfig(level=level)
            assert config.level == level


class TestConfig:
    """Tests for main Config model."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = Config()
        assert config.default_mode == "tui"
        assert config.interval == 1.0
        assert isinstance(config.tui, TUIConfig)
        assert isinstance(config.cli, CLIConfig)
        assert isinstance(config.display, DisplayConfig)
        assert isinstance(config.plugins, PluginsConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_interval_bounds(self) -> None:
        """Test interval validation."""
        with pytest.raises(ValidationError):
            Config(interval=0.05)

        with pytest.raises(ValidationError):
            Config(interval=4000)

    def test_valid_modes(self) -> None:
        """Test valid mode values."""
        for mode in ["tui", "cli"]:
            config = Config(default_mode=mode)
            assert config.default_mode == mode

    def test_get_pane_config(self) -> None:
        """Test get_pane_config method."""
        config = Config(tui=TUIConfig(panes={"cpu": {"enabled": True, "refresh_interval": 2.0}}))
        cpu_config = config.get_pane_config("cpu")
        assert cpu_config.enabled is True
        assert cpu_config.refresh_interval == 2.0

        # Non-existent pane returns default
        other = config.get_pane_config("nonexistent")
        assert other.enabled is True
        assert other.refresh_interval == 1.0

    def test_get_plugin_config(self) -> None:
        """Test get_plugin_config method."""
        config = Config(
            plugins=PluginsConfig(plugin_config={"docker": {"socket": "/var/run/docker.sock"}})
        )
        docker_config = config.get_plugin_config("docker")
        assert docker_config == {"socket": "/var/run/docker.sock"}

        # Non-existent plugin returns empty dict
        other = config.get_plugin_config("nonexistent")
        assert other == {}


class TestGetConfigPath:
    """Tests for get_config_path function."""

    def test_custom_path_exists(self) -> None:
        """Test custom path is returned when it exists."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"default_mode: cli")
            temp_path = f.name

        try:
            result = get_config_path(temp_path)
            assert result == Path(temp_path)
        finally:
            os.unlink(temp_path)

    def test_custom_path_not_exists(self) -> None:
        """Test error when custom path doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            get_config_path("/nonexistent/config.yaml")

    def test_env_var_path(self) -> None:
        """Test UPTOP_CONFIG_PATH environment variable."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"default_mode: cli")
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"UPTOP_CONFIG_PATH": temp_path}):
                result = get_config_path()
                assert result == Path(temp_path)
        finally:
            os.unlink(temp_path)

    def test_env_var_path_not_exists(self) -> None:
        """Test env var path that doesn't exist returns None."""
        with patch.dict(os.environ, {"UPTOP_CONFIG_PATH": "/nonexistent/path.yaml"}):
            result = get_config_path()
            assert result is None

    def test_xdg_path(self) -> None:
        """Test XDG config path discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "uptop"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.yaml"
            config_file.write_text("default_mode: cli")

            # Mock home directory
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Clear env var
                env = os.environ.copy()
                env.pop("UPTOP_CONFIG_PATH", None)
                with patch.dict(os.environ, env, clear=True):
                    result = get_config_path()
                    assert result == config_file

    def test_no_config_found(self) -> None:
        """Test None returned when no config exists."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(Path, "home", return_value=Path(tmpdir)),
        ):
            env = os.environ.copy()
            env.pop("UPTOP_CONFIG_PATH", None)
            with patch.dict(os.environ, env, clear=True):
                result = get_config_path()
                assert result is None


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_defaults(self) -> None:
        """Test loading defaults when no config file exists."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(Path, "home", return_value=Path(tmpdir)),
        ):
            env = os.environ.copy()
            env.pop("UPTOP_CONFIG_PATH", None)
            with patch.dict(os.environ, env, clear=True):
                config = load_config()
                assert config.default_mode == "tui"
                assert config.interval == 1.0

    def test_load_from_file(self) -> None:
        """Test loading config from file."""
        yaml_content = """
default_mode: cli
interval: 2.5
tui:
  theme: solarized
  mouse_enabled: false
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = load_config(config_path=temp_path)
            assert config.default_mode == "cli"
            assert config.interval == 2.5
            assert config.tui.theme == "solarized"
            assert config.tui.mouse_enabled is False
        finally:
            os.unlink(temp_path)

    def test_load_with_cli_overrides(self) -> None:
        """Test CLI overrides are applied."""
        config = load_config(
            cli_overrides={
                "interval": 5.0,
                "tui": {"theme": "nord"},
            }
        )
        assert config.interval == 5.0
        assert config.tui.theme == "nord"

    def test_cli_overrides_trump_file(self) -> None:
        """Test CLI overrides take precedence over file."""
        yaml_content = """
interval: 2.0
tui:
  theme: light
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = load_config(
                config_path=temp_path,
                cli_overrides={"interval": 10.0},
            )
            assert config.interval == 10.0
            assert config.tui.theme == "light"  # From file, not overridden
        finally:
            os.unlink(temp_path)

    def test_env_var_expansion(self) -> None:
        """Test environment variables are expanded."""
        yaml_content = """
plugins:
  plugin_config:
    weather:
      api_key: ${WEATHER_API_KEY}
process_filters:
  my_user: "username == '${USER}'"
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"WEATHER_API_KEY": "secret123", "USER": "testuser"}):
                config = load_config(config_path=temp_path)
                assert config.plugins.plugin_config["weather"]["api_key"] == "secret123"
                assert config.process_filters["my_user"] == "username == 'testuser'"
        finally:
            os.unlink(temp_path)

    def test_partial_config_file(self) -> None:
        """Test that partial config file is merged with defaults."""
        yaml_content = """
tui:
  theme: gruvbox
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = load_config(config_path=temp_path)
            # Custom value from file
            assert config.tui.theme == "gruvbox"
            # Defaults still present
            assert config.default_mode == "tui"
            assert config.interval == 1.0
            assert config.tui.mouse_enabled is True
        finally:
            os.unlink(temp_path)

    def test_invalid_yaml(self) -> None:
        """Test error on invalid YAML."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name

        try:
            with pytest.raises(ConfigSyntaxError):
                load_config(config_path=temp_path)
        finally:
            os.unlink(temp_path)

    def test_invalid_config_values(self) -> None:
        """Test error on invalid config values."""
        yaml_content = """
interval: -5
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            with pytest.raises(ConfigValidationError):
                load_config(config_path=temp_path)
        finally:
            os.unlink(temp_path)


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_default_config_is_valid(self) -> None:
        """Test that DEFAULT_CONFIG produces a valid Config."""
        config = Config(**DEFAULT_CONFIG)
        assert config.default_mode == "tui"
        assert config.interval == 1.0

    def test_default_config_has_all_sections(self) -> None:
        """Test DEFAULT_CONFIG contains all required sections."""
        assert "default_mode" in DEFAULT_CONFIG
        assert "interval" in DEFAULT_CONFIG
        assert "tui" in DEFAULT_CONFIG
        assert "cli" in DEFAULT_CONFIG
        assert "display" in DEFAULT_CONFIG
        assert "plugins" in DEFAULT_CONFIG
        assert "process_filters" in DEFAULT_CONFIG
        assert "logging" in DEFAULT_CONFIG

    def test_default_config_panes(self) -> None:
        """Test DEFAULT_CONFIG contains pane configurations."""
        panes = DEFAULT_CONFIG["tui"]["panes"]
        assert "cpu" in panes
        assert "memory" in panes
        assert "processes" in panes
        assert "network" in panes
        assert "disk" in panes
        assert "gpu" in panes
        assert "sensors" in panes
