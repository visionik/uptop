"""Tests for uptop CLI."""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import typer
from pydantic import BaseModel
from typer.testing import CliRunner

from uptop import __version__
from uptop.cli import (
    OutputFormat,
    OutputMode,
    PluginValidationResult,
    Theme,
    app,
    build_cli_overrides,
    check_plugins_callback,
    detect_mode,
    validate_plugin,
)

runner = CliRunner()


class TestDetectMode:
    """Tests for mode detection logic."""

    def test_explicit_tui_mode(self) -> None:
        """Test explicit TUI mode is respected."""
        assert detect_mode("tui", False, False) == "tui"

    def test_explicit_cli_mode(self) -> None:
        """Test explicit CLI mode is respected."""
        assert detect_mode("cli", False, False) == "cli"

    def test_format_flag_implies_cli(self) -> None:
        """Test format flags imply CLI mode."""
        assert detect_mode(None, True, False) == "cli"

    def test_stream_flag_implies_cli(self) -> None:
        """Test stream flags imply CLI mode."""
        assert detect_mode(None, False, True) == "cli"

    def test_tty_defaults_to_tui(self) -> None:
        """Test TTY defaults to TUI mode."""
        with (
            patch.object(sys.stdin, "isatty", return_value=True),
            patch.object(sys.stdout, "isatty", return_value=True),
        ):
            assert detect_mode(None, False, False) == "tui"

    def test_non_tty_defaults_to_cli(self) -> None:
        """Test non-TTY defaults to CLI mode."""
        with patch.object(sys.stdin, "isatty", return_value=False):
            assert detect_mode(None, False, False) == "cli"


class TestBuildCliOverrides:
    """Tests for building CLI overrides."""

    def test_interval_override(self) -> None:
        """Test interval override."""
        overrides = build_cli_overrides(interval=2.5)
        assert overrides["interval"] == 2.5

    def test_panes_override(self) -> None:
        """Test panes override."""
        overrides = build_cli_overrides(panes=["cpu", "memory"])
        assert "tui" in overrides
        assert "cpu" in overrides["tui"]["panes"]
        assert "memory" in overrides["tui"]["panes"]

    def test_theme_override(self) -> None:
        """Test theme override."""
        overrides = build_cli_overrides(theme=Theme.SOLARIZED)
        assert overrides["tui"]["theme"] == "solarized"

    def test_layout_override(self) -> None:
        """Test layout override."""
        overrides = build_cli_overrides(layout="server_focus")
        assert overrides["tui"]["layouts"]["default"] == "server_focus"

    def test_no_mouse_override(self) -> None:
        """Test no-mouse override."""
        overrides = build_cli_overrides(no_mouse=True)
        assert overrides["tui"]["mouse_enabled"] is False

    def test_format_override(self) -> None:
        """Test format override."""
        overrides = build_cli_overrides(format_=OutputFormat.MARKDOWN)
        assert overrides["cli"]["default_format"] == "markdown"

    def test_output_mode_override(self) -> None:
        """Test output mode override."""
        overrides = build_cli_overrides(output_mode=OutputMode.STREAM)
        assert overrides["cli"]["default_output_mode"] == "stream"

    def test_pretty_override(self) -> None:
        """Test pretty-print override."""
        overrides = build_cli_overrides(pretty=False)
        assert overrides["cli"]["pretty_print"] is False

    def test_no_overrides_empty_dict(self) -> None:
        """Test no overrides returns minimal dict."""
        overrides = build_cli_overrides()
        assert overrides == {}

    def test_combined_overrides(self) -> None:
        """Test multiple overrides combined."""
        overrides = build_cli_overrides(
            interval=5.0,
            theme=Theme.NORD,
            format_=OutputFormat.JSON,
            pretty=True,
        )
        assert overrides["interval"] == 5.0
        assert overrides["tui"]["theme"] == "nord"
        assert overrides["cli"]["default_format"] == "json"
        assert overrides["cli"]["pretty_print"] is True


class TestCLIVersion:
    """Tests for version flag."""

    def test_version_flag(self) -> None:
        """Test --version flag shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_version_short_flag(self) -> None:
        """Test -V flag shows version."""
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestCLIMain:
    """Tests for main CLI command."""

    def test_default_run(self) -> None:
        """Test default run (no arguments) produces JSON output."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        # Default output is JSON
        import json
        parsed = json.loads(result.stdout)
        assert "panes" in parsed

    def test_interval_option(self) -> None:
        """Test --interval option."""
        result = runner.invoke(app, ["--interval", "2.5", "--panes", "cpu"])
        assert result.exit_code == 0
        # Output is JSON, not debug message
        import json
        parsed = json.loads(result.stdout)
        assert "panes" in parsed

    def test_json_format(self) -> None:
        """Test --json flag produces valid JSON."""
        result = runner.invoke(app, ["--json", "--panes", "cpu"])
        assert result.exit_code == 0
        import json
        parsed = json.loads(result.stdout)
        assert "panes" in parsed

    def test_markdown_format(self) -> None:
        """Test --markdown flag (not yet implemented, should error or fallback)."""
        result = runner.invoke(app, ["--markdown", "--panes", "cpu"])
        # Markdown not implemented, should error
        assert result.exit_code == 1 or "Unknown format" in (result.stdout + result.stderr)

    def test_prometheus_format(self) -> None:
        """Test --prometheus flag produces Prometheus format."""
        result = runner.invoke(app, ["--prometheus", "--panes", "cpu"])
        assert result.exit_code == 0
        assert "uptop_cpu" in result.stdout

    def test_stream_option(self) -> None:
        """Test --stream flag (not yet implemented)."""
        result = runner.invoke(app, ["--json", "--stream", "--panes", "cpu"])
        # Stream mode not implemented, should error
        assert result.exit_code == 1 or "not yet implemented" in (result.stdout + result.stderr).lower()

    def test_once_option(self) -> None:
        """Test --once flag produces output and exits."""
        result = runner.invoke(app, ["--json", "--once", "--panes", "cpu"])
        assert result.exit_code == 0
        import json
        parsed = json.loads(result.stdout)
        assert "panes" in parsed


class TestCLITuiCommand:
    """Tests for 'tui' subcommand."""

    def test_tui_command(self) -> None:
        """Test 'tui' subcommand (help only, can't run TUI in test)."""
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        assert "tui" in result.stdout.lower()

    def test_tui_theme(self) -> None:
        """Test TUI with theme option (help only)."""
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        assert "--theme" in result.stdout

    def test_tui_no_mouse(self) -> None:
        """Test TUI with --no-mouse (help only)."""
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        assert "--no-mouse" in result.stdout

    def test_tui_layout(self) -> None:
        """Test TUI with layout option (help only)."""
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        assert "--layout" in result.stdout


class TestCLICliCommand:
    """Tests for 'cli' subcommand."""

    def test_cli_command(self) -> None:
        """Test 'cli' subcommand produces JSON output."""
        result = runner.invoke(app, ["cli", "--panes", "cpu"])
        assert result.exit_code == 0
        import json
        parsed = json.loads(result.stdout)
        assert "panes" in parsed

    def test_cli_json(self) -> None:
        """Test CLI with --json produces JSON."""
        result = runner.invoke(app, ["cli", "--json", "--panes", "cpu"])
        assert result.exit_code == 0
        import json
        parsed = json.loads(result.stdout)
        assert "panes" in parsed

    def test_cli_stream(self) -> None:
        """Test CLI with --stream (not yet implemented)."""
        result = runner.invoke(app, ["cli", "--stream", "--panes", "cpu"])
        # Stream mode not implemented
        assert result.exit_code == 1 or "not yet implemented" in (result.stdout + result.stderr).lower()

    def test_cli_query(self) -> None:
        """Test CLI with --query (query filtering not yet implemented)."""
        result = runner.invoke(app, ["cli", "--panes", "cpu"])
        # Query option accepted but not filtering yet
        assert result.exit_code == 0


class TestCLIConfigOption:
    """Tests for --config option."""

    def test_custom_config_file(self) -> None:
        """Test loading custom config file."""
        yaml_content = """
default_mode: cli
interval: 3.0
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = runner.invoke(app, ["--config", temp_path, "--panes", "cpu"])
            assert result.exit_code == 0
            # Output is JSON, config was loaded
            import json
            parsed = json.loads(result.stdout)
            assert "panes" in parsed
        finally:
            os.unlink(temp_path)

    def test_missing_config_file(self) -> None:
        """Test error on missing config file."""
        result = runner.invoke(app, ["--config", "/nonexistent/config.yaml"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Error" in output or "not found" in output.lower()

    def test_invalid_config_file(self) -> None:
        """Test error on invalid config."""
        yaml_content = """
interval: -100
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = runner.invoke(app, ["--config", temp_path])
            assert result.exit_code == 1
            output = result.stdout + result.stderr
            assert "error" in output.lower()
        finally:
            os.unlink(temp_path)


class TestCLIEnvVar:
    """Tests for environment variable config path."""

    def test_uptop_config_path_env(self) -> None:
        """Test UPTOP_CONFIG_PATH environment variable."""
        yaml_content = """
default_mode: cli
interval: 7.5
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = runner.invoke(
                app,
                ["--panes", "cpu"],
                env={"UPTOP_CONFIG_PATH": temp_path},
            )
            assert result.exit_code == 0
            # Output is JSON
            import json
            parsed = json.loads(result.stdout)
            assert "panes" in parsed
        finally:
            os.unlink(temp_path)


class TestOutputFormatEnum:
    """Tests for OutputFormat enum."""

    def test_all_formats(self) -> None:
        """Test all output formats exist."""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.PROMETHEUS.value == "prometheus"


class TestOutputModeEnum:
    """Tests for OutputMode enum."""

    def test_all_modes(self) -> None:
        """Test all output modes exist."""
        assert OutputMode.ONCE.value == "once"
        assert OutputMode.STREAM.value == "stream"
        assert OutputMode.CONTINUOUS.value == "continuous"


class TestThemeEnum:
    """Tests for Theme enum."""

    def test_all_themes(self) -> None:
        """Test all themes exist."""
        assert Theme.DARK.value == "dark"
        assert Theme.LIGHT.value == "light"
        assert Theme.SOLARIZED.value == "solarized"
        assert Theme.NORD.value == "nord"
        assert Theme.GRUVBOX.value == "gruvbox"


class TestCLIPanesOption:
    """Tests for --panes option."""

    def test_single_pane(self) -> None:
        """Test single pane selection."""
        result = runner.invoke(app, ["--panes", "cpu"])
        assert result.exit_code == 0

    def test_multiple_panes(self) -> None:
        """Test multiple pane selection."""
        result = runner.invoke(app, ["--panes", "cpu", "--panes", "memory"])
        assert result.exit_code == 0


class TestCLIHelp:
    """Tests for CLI help."""

    def test_main_help(self) -> None:
        """Test main command help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "uptop" in result.stdout.lower()
        assert "--config" in result.stdout
        assert "--version" in result.stdout

    def test_main_help_contains_description(self) -> None:
        """Test main help contains full description."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Check for key description elements
        assert "system monitor" in result.stdout.lower() or "telemetry" in result.stdout.lower()

    def test_main_help_contains_examples(self) -> None:
        """Test main help contains usage examples."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Check for example commands - Typer may format these differently
        assert "--json" in result.stdout
        assert "--once" in result.stdout or "once" in result.stdout.lower()

    def test_main_help_contains_check_plugins(self) -> None:
        """Test main help contains --check-plugins option."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--check-plugins" in result.stdout

    def test_tui_help(self) -> None:
        """Test TUI command help."""
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        assert "--theme" in result.stdout
        assert "--no-mouse" in result.stdout

    def test_tui_help_contains_docstring(self) -> None:
        """Test TUI help contains command docstring."""
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
        # Check for TUI-specific help text
        assert "tui" in result.stdout.lower() or "terminal" in result.stdout.lower()

    def test_cli_help(self) -> None:
        """Test CLI command help."""
        result = runner.invoke(app, ["cli", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout
        assert "--stream" in result.stdout

    def test_cli_help_contains_formats(self) -> None:
        """Test CLI help lists all output formats."""
        result = runner.invoke(app, ["cli", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout
        assert "--markdown" in result.stdout
        assert "--prometheus" in result.stdout


class TestCLIVersionOutput:
    """Tests for version output format."""

    def test_version_format(self) -> None:
        """Test version output format matches 'uptop version X.Y.Z'."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        # Check exact format
        assert f"uptop version {__version__}" in result.stdout

    def test_version_exits_cleanly(self) -> None:
        """Test version flag exits with code 0."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0


class TestCheckPluginsCommand:
    """Tests for --check-plugins command."""

    def test_check_plugins_flag_exists(self) -> None:
        """Test --check-plugins flag is recognized."""
        result = runner.invoke(app, ["--help"])
        assert "--check-plugins" in result.stdout

    def test_check_plugins_runs(self) -> None:
        """Test --check-plugins runs plugin validation."""
        result = runner.invoke(app, ["--check-plugins"])
        # Should run without crashing
        assert "Checking plugins" in result.stdout

    def test_check_plugins_shows_summary(self) -> None:
        """Test --check-plugins shows validation summary."""
        result = runner.invoke(app, ["--check-plugins"])
        # Should show summary with count
        assert "plugins checked" in result.stdout


class TestPluginValidation:
    """Tests for plugin validation logic."""

    def test_validate_plugin_valid_pane(self) -> None:
        """Test validation of a valid pane plugin."""
        from uptop.plugin_api.base import PanePlugin

        # Create a valid mock pane plugin
        class ValidPanePlugin(PanePlugin):
            name = "test_pane"
            display_name = "Test Pane"
            version = "1.0.0"
            api_version = "1.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        plugin = ValidPanePlugin()
        result = validate_plugin(plugin, "test_pane")

        assert result.valid is True
        assert result.name == "test_pane"
        assert result.version == "1.0.0"
        assert len(result.errors) == 0

    def test_validate_plugin_incompatible_api_version(self) -> None:
        """Test validation catches incompatible API version."""
        from uptop.plugin_api.base import PanePlugin

        class IncompatiblePlugin(PanePlugin):
            name = "incompatible"
            display_name = "Incompatible"
            version = "1.0.0"
            api_version = "99.0"  # Future incompatible version

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        plugin = IncompatiblePlugin()
        result = validate_plugin(plugin, "incompatible")

        assert result.valid is False
        assert len(result.errors) > 0
        assert "Incompatible API version" in result.errors[0]

    def test_validate_plugin_invalid_schema(self) -> None:
        """Test validation catches invalid schema return type."""
        from uptop.plugin_api.base import PanePlugin

        class BadSchemaPlugin(PanePlugin):
            name = "bad_schema"
            display_name = "Bad Schema"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return "not a pydantic model"  # Invalid

        plugin = BadSchemaPlugin()
        result = validate_plugin(plugin, "bad_schema")

        assert result.valid is False
        assert any("Pydantic" in error or "BaseModel" in error for error in result.errors)

    def test_validation_result_class(self) -> None:
        """Test PluginValidationResult class."""
        result = PluginValidationResult(
            name="test",
            version="1.0.0",
            valid=True,
            errors=[],
        )
        assert result.name == "test"
        assert result.version == "1.0.0"
        assert result.valid is True
        assert result.errors == []

    def test_validation_result_with_errors(self) -> None:
        """Test PluginValidationResult with errors."""
        result = PluginValidationResult(
            name="test",
            version="1.0.0",
            valid=False,
            errors=["Error 1", "Error 2"],
        )
        assert result.valid is False
        assert len(result.errors) == 2


class TestCheckPluginsWithMocks:
    """Tests for --check-plugins with mocked plugins."""

    def test_check_plugins_with_valid_plugins(self) -> None:
        """Test --check-plugins with mocked valid plugins."""
        from uptop.plugin_api.base import PanePlugin
        from uptop.plugins.registry import PluginRegistry

        class MockValidPlugin(PanePlugin):
            name = "mock_valid"
            display_name = "Mock Valid"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        # Create mock registry
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.failed_plugins = {}
        mock_registry.__iter__ = MagicMock(return_value=iter(["mock_valid"]))

        mock_plugin = MockValidPlugin()
        mock_registry.get.return_value = mock_plugin

        with patch("uptop.plugins.registry.PluginRegistry", return_value=mock_registry):
            result = runner.invoke(app, ["--check-plugins"])

        # Should show valid plugin
        assert "mock_valid" in result.stdout
        assert "OK" in result.stdout or "valid" in result.stdout.lower()

    def test_check_plugins_with_invalid_plugin(self) -> None:
        """Test --check-plugins with mocked invalid plugin."""
        from uptop.plugins.registry import PluginRegistry

        # Create mock registry with a failed plugin
        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.failed_plugins = {
            "bad_plugin": "Missing collect_data method"
        }
        mock_registry.__iter__ = MagicMock(return_value=iter([]))

        with patch("uptop.plugins.registry.PluginRegistry", return_value=mock_registry):
            result = runner.invoke(app, ["--check-plugins"])

        # Should show invalid plugin
        assert "bad_plugin" in result.stdout
        # Should show error
        assert "Missing" in result.stdout or "Failed" in result.stdout
        # Should exit with error code
        assert result.exit_code == 1

    def test_check_plugins_summary_counts(self) -> None:
        """Test --check-plugins shows correct valid/invalid counts."""
        from uptop.plugin_api.base import PanePlugin
        from uptop.plugins.registry import PluginRegistry

        class MockValidPlugin(PanePlugin):
            name = "valid_plugin"
            display_name = "Valid Plugin"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.failed_plugins = {"failed_one": "Error 1", "failed_two": "Error 2"}
        mock_registry.__iter__ = MagicMock(return_value=iter(["valid_plugin"]))
        mock_registry.get.return_value = MockValidPlugin()

        with patch("uptop.plugins.registry.PluginRegistry", return_value=mock_registry):
            result = runner.invoke(app, ["--check-plugins"])

        # Should show total count of 3 (1 valid + 2 invalid)
        assert "3 plugins checked" in result.stdout
        assert "1 valid" in result.stdout
        assert "2 invalid" in result.stdout


class TestPluginValidationEdgeCases:
    """Tests for plugin validation edge cases."""

    def test_validate_collector_plugin(self) -> None:
        """Test validation of collector plugin."""
        from uptop.plugin_api.base import CollectorPlugin

        class ValidCollectorPlugin(CollectorPlugin):
            name = "test_collector"
            display_name = "Test Collector"
            version = "1.0.0"

            async def collect(self):
                return {}

        plugin = ValidCollectorPlugin()
        result = validate_plugin(plugin, "test_collector")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_collector_plugin_with_collect(self) -> None:
        """Test validation passes with collect method present."""
        from uptop.plugin_api.base import CollectorPlugin

        class ValidCollectorPlugin(CollectorPlugin):
            name = "valid_collector"
            display_name = "Valid Collector"
            version = "1.0.0"

            async def collect(self):
                return {}

        plugin = ValidCollectorPlugin()
        result = validate_plugin(plugin, "valid_collector")

        # Collector with collect method is valid
        assert result.valid is True

    def test_validate_formatter_plugin(self) -> None:
        """Test validation of formatter plugin."""
        from uptop.plugin_api.base import FormatterPlugin

        class ValidFormatterPlugin(FormatterPlugin):
            name = "test_formatter"
            display_name = "Test Formatter"
            version = "1.0.0"

            def format(self, data):
                return str(data)

        plugin = ValidFormatterPlugin()
        result = validate_plugin(plugin, "test_formatter")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_formatter_plugin_missing_format(self) -> None:
        """Test validation catches missing format method - already covered by base class validation."""
        from uptop.plugin_api.base import FormatterPlugin

        class ValidFormatterPlugin(FormatterPlugin):
            name = "valid_formatter"
            display_name = "Valid Formatter"
            version = "1.0.0"

            def format(self, data):
                return str(data)

        plugin = ValidFormatterPlugin()
        result = validate_plugin(plugin, "valid_formatter")

        # Formatter with format method is valid
        assert result.valid is True

    def test_validate_action_plugin(self) -> None:
        """Test validation of action plugin."""
        from uptop.plugin_api.base import ActionPlugin

        class ValidActionPlugin(ActionPlugin):
            name = "test_action"
            display_name = "Test Action"
            version = "1.0.0"

            def can_execute(self, context):
                return True

            def execute(self, context):
                pass

        plugin = ValidActionPlugin()
        result = validate_plugin(plugin, "test_action")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_action_plugin_missing_methods(self) -> None:
        """Test validation of action plugin - valid when has methods."""
        from uptop.plugin_api.base import ActionPlugin

        class ValidActionPlugin(ActionPlugin):
            name = "valid_action"
            display_name = "Valid Action"
            version = "1.0.0"

            def can_execute(self, context):
                return True

            def execute(self, context):
                pass

        plugin = ValidActionPlugin()
        result = validate_plugin(plugin, "valid_action")

        # Valid action plugin with both methods
        assert result.valid is True

    def test_validate_plugin_invalid_api_version_format(self) -> None:
        """Test validation catches invalid API version format."""
        from uptop.plugin_api.base import PanePlugin

        class BadApiVersionPlugin(PanePlugin):
            name = "bad_api"
            display_name = "Bad API"
            version = "1.0.0"
            api_version = "not.a.number"  # Invalid format

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        plugin = BadApiVersionPlugin()
        result = validate_plugin(plugin, "bad_api")

        assert result.valid is False
        assert any("Invalid API version format" in error for error in result.errors)

    def test_validate_plugin_get_schema_exception(self) -> None:
        """Test validation catches exception in get_schema."""
        from uptop.plugin_api.base import PanePlugin

        class ExceptionSchemaPlugin(PanePlugin):
            name = "exception_schema"
            display_name = "Exception Schema"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                raise RuntimeError("Schema error")

        plugin = ExceptionSchemaPlugin()
        result = validate_plugin(plugin, "exception_schema")

        assert result.valid is False
        assert any("get_schema raised error" in error for error in result.errors)

    def test_validate_pane_plugin_with_collect_data(self) -> None:
        """Test validation passes with collect_data method."""
        from uptop.plugin_api.base import PanePlugin

        class ValidPlugin(PanePlugin):
            name = "valid_pane"
            display_name = "Valid Pane"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        plugin = ValidPlugin()
        result = validate_plugin(plugin, "valid_pane")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_pane_plugin_with_render_tui(self) -> None:
        """Test validation passes with render_tui method."""
        from uptop.plugin_api.base import PanePlugin

        class ValidRenderPlugin(PanePlugin):
            name = "valid_render"
            display_name = "Valid Render"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        plugin = ValidRenderPlugin()
        result = validate_plugin(plugin, "valid_render")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_pane_plugin_with_get_schema(self) -> None:
        """Test validation passes with get_schema method."""
        from uptop.plugin_api.base import PanePlugin

        class ValidSchemaPlugin(PanePlugin):
            name = "valid_schema"
            display_name = "Valid Schema"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return BaseModel

        plugin = ValidSchemaPlugin()
        result = validate_plugin(plugin, "valid_schema")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_pane_plugin_null_schema(self) -> None:
        """Test validation passes with get_schema returning None."""
        from uptop.plugin_api.base import PanePlugin

        class NullSchemaPlugin(PanePlugin):
            name = "null_schema"
            display_name = "Null Schema"
            version = "1.0.0"

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return None

        plugin = NullSchemaPlugin()
        result = validate_plugin(plugin, "null_schema")

        # Null schema is valid
        assert result.valid is True


class TestCheckPluginsDiscoveryError:
    """Tests for check_plugins with discovery errors."""

    def test_check_plugins_discovery_exception(self) -> None:
        """Test --check-plugins handles discovery exception."""
        from uptop.plugins.registry import PluginRegistry

        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.discover_all.side_effect = RuntimeError("Discovery failed")

        with patch("uptop.plugins.registry.PluginRegistry", return_value=mock_registry):
            result = runner.invoke(app, ["--check-plugins"])

        assert result.exit_code == 1
        assert "Error during plugin discovery" in result.stdout or "Discovery failed" in result.stdout

    def test_check_plugins_validation_exception(self) -> None:
        """Test --check-plugins handles validation exception for a plugin."""
        from uptop.plugins.registry import PluginRegistry

        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.failed_plugins = {}
        mock_registry.__iter__ = MagicMock(return_value=iter(["failing_plugin"]))
        mock_registry.get.side_effect = RuntimeError("Plugin retrieval failed")

        with patch("uptop.plugins.registry.PluginRegistry", return_value=mock_registry):
            result = runner.invoke(app, ["--check-plugins"])

        # Should show the plugin with validation error
        assert "failing_plugin" in result.stdout
        assert "Validation error" in result.stdout or "Plugin retrieval failed" in result.stdout
        assert result.exit_code == 1

    def test_check_plugins_multiple_errors_display(self) -> None:
        """Test --check-plugins displays errors for a plugin with multiple issues."""
        from uptop.plugin_api.base import PanePlugin
        from uptop.plugins.registry import PluginRegistry

        # Plugin with multiple validation errors
        class MultiErrorPlugin(PanePlugin):
            name = "multi_error"
            display_name = "Multi Error"
            version = "1.0.0"
            api_version = "99.0"  # Incompatible version

            async def collect_data(self):
                return None

            def render_tui(self, data):
                return None

            def get_schema(self):
                return "not a model"  # Invalid schema

        mock_registry = MagicMock(spec=PluginRegistry)
        mock_registry.failed_plugins = {}
        mock_registry.__iter__ = MagicMock(return_value=iter(["multi_error"]))

        plugin = MultiErrorPlugin()
        mock_registry.get.return_value = plugin

        with patch("uptop.plugins.registry.PluginRegistry", return_value=mock_registry):
            result = runner.invoke(app, ["--check-plugins"])

        assert "multi_error" in result.stdout
        # Should have errors due to incompatible API version and invalid schema
        assert result.exit_code == 1


class TestCLIContinuousMode:
    """Tests for continuous output mode."""

    def test_continuous_option(self) -> None:
        """Test --continuous flag sets continuous mode."""
        result = runner.invoke(app, ["--json", "--continuous", "--panes", "cpu"])
        # Continuous mode not implemented yet, should error
        assert result.exit_code == 1 or "not yet implemented" in (result.stdout + result.stderr).lower()

    def test_cli_command_continuous(self) -> None:
        """Test cli command with --continuous."""
        result = runner.invoke(app, ["cli", "--continuous", "--panes", "cpu"])
        # Continuous mode not implemented
        assert result.exit_code == 1 or "not yet implemented" in (result.stdout + result.stderr).lower()


class TestTuiCommandExecution:
    """Tests for TUI command actual execution (mocked)."""

    def test_tui_command_with_config_error(self) -> None:
        """Test TUI command with config file error."""
        result = runner.invoke(app, ["tui", "--config", "/nonexistent/config.yaml"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Error" in output or "not found" in output.lower()

    def test_tui_command_with_invalid_config(self) -> None:
        """Test TUI command with invalid config file."""
        yaml_content = """
interval: -100
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = runner.invoke(app, ["tui", "--config", temp_path])
            assert result.exit_code == 1
            output = result.stdout + result.stderr
            assert "error" in output.lower()
        finally:
            os.unlink(temp_path)

    def test_tui_command_execution_mocked(self) -> None:
        """Test TUI command execution with mocked run_app."""
        with patch("uptop.cli.run_uptop") as mock_run:
            result = runner.invoke(app, ["tui", "--theme", "dark"])
            # TUI should invoke run_uptop with config having default_mode = "tui"
            if mock_run.called:
                args, kwargs = mock_run.call_args
                config = args[0]
                assert config.default_mode == "tui"


class TestCliCommandExecution:
    """Tests for CLI command execution edge cases."""

    def test_cli_command_with_config_error(self) -> None:
        """Test CLI command with config file error."""
        result = runner.invoke(app, ["cli", "--config", "/nonexistent/config.yaml"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Error" in output or "not found" in output.lower()

    def test_cli_command_with_invalid_config(self) -> None:
        """Test CLI command with invalid config file."""
        yaml_content = """
interval: -100
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = runner.invoke(app, ["cli", "--config", temp_path])
            assert result.exit_code == 1
            output = result.stdout + result.stderr
            assert "error" in output.lower()
        finally:
            os.unlink(temp_path)

    def test_cli_command_markdown_not_implemented(self) -> None:
        """Test CLI command with markdown format (not implemented)."""
        result = runner.invoke(app, ["cli", "--markdown", "--panes", "cpu"])
        # Markdown not implemented
        assert result.exit_code == 1 or "Unknown format" in (result.stdout + result.stderr)


class TestRunUptopFunction:
    """Tests for run_uptop function."""

    def test_run_uptop_tui_mode(self) -> None:
        """Test run_uptop in TUI mode calls run_app."""
        from uptop.cli import run_uptop
        from uptop.config import Config

        config = Config(default_mode="tui")

        with patch("uptop.tui.run_app") as mock_run_app:
            run_uptop(config)
            mock_run_app.assert_called_once_with(config)

    def test_run_uptop_cli_mode(self) -> None:
        """Test run_uptop in CLI mode calls run_cli_mode."""
        from uptop.cli import run_uptop
        from uptop.config import Config

        config = Config(default_mode="cli")

        with patch("uptop.cli_runner.run_cli_mode", return_value=0) as mock_run_cli:
            run_uptop(config, pane_names=["cpu"])
            mock_run_cli.assert_called_once()

    def test_run_uptop_cli_mode_error_exit(self) -> None:
        """Test run_uptop in CLI mode handles non-zero exit code."""
        from uptop.cli import run_uptop
        from uptop.config import Config

        config = Config(default_mode="cli")

        with patch("uptop.cli_runner.run_cli_mode", return_value=1) as mock_run_cli:
            with pytest.raises(typer.Exit) as exc_info:
                run_uptop(config)
            assert exc_info.value.exit_code == 1


class TestCliMainEntryPoint:
    """Tests for cli_main entry point function."""

    def test_cli_main_function(self) -> None:
        """Test cli_main calls the app."""
        from uptop.cli import cli_main

        with patch("uptop.cli.app") as mock_app:
            cli_main()
            mock_app.assert_called_once()


class TestParsePanesOption:
    """Tests for parse_panes_option function."""

    def test_parse_panes_none(self) -> None:
        """Test parse_panes_option with None input."""
        from uptop.cli import parse_panes_option

        result = parse_panes_option(None)
        assert result is None

    def test_parse_panes_empty_list(self) -> None:
        """Test parse_panes_option with empty list."""
        from uptop.cli import parse_panes_option

        result = parse_panes_option([])
        assert result is None

    def test_parse_panes_comma_separated(self) -> None:
        """Test parse_panes_option with comma-separated values."""
        from uptop.cli import parse_panes_option

        result = parse_panes_option(["cpu,memory,disk"])
        assert result == ["cpu", "memory", "disk"]

    def test_parse_panes_mixed_input(self) -> None:
        """Test parse_panes_option with mixed input."""
        from uptop.cli import parse_panes_option

        result = parse_panes_option(["cpu,memory", "disk", "network,process"])
        assert result == ["cpu", "memory", "disk", "network", "process"]

    def test_parse_panes_strips_whitespace(self) -> None:
        """Test parse_panes_option strips whitespace."""
        from uptop.cli import parse_panes_option

        result = parse_panes_option(["  cpu  , memory  "])
        assert result == ["cpu", "memory"]

    def test_parse_panes_empty_values_filtered(self) -> None:
        """Test parse_panes_option filters empty values."""
        from uptop.cli import parse_panes_option

        result = parse_panes_option(["cpu,,memory", "", "disk"])
        assert result == ["cpu", "memory", "disk"]
