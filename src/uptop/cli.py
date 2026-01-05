"""Command-line interface for uptop.

This module provides:
- Typer-based CLI application
- Hybrid mode detection (TUI vs CLI)
- Config file loading with CLI overrides
- All command-line flags and options
- Plugin validation via --check-plugins

Usage:
    uptop                    # TUI mode (default if TTY)
    uptop tui                # Explicit TUI mode
    uptop cli --json         # Explicit CLI mode
    uptop --json             # Inferred CLI mode (format flag present)
    uptop --check-plugins    # Validate all registered plugins

Examples:
    # Start interactive TUI monitor
    uptop

    # Output system metrics as JSON (single snapshot)
    uptop --json --once

    # Stream metrics continuously in Prometheus format
    uptop --prometheus --stream --interval 5

    # Use a custom configuration file
    uptop --config ~/.config/uptop/custom.yaml

    # Check all plugins for compatibility issues
    uptop --check-plugins
"""

from enum import Enum
from pathlib import Path
import sys
from typing import Annotated, Any

from pydantic import BaseModel
from rich.console import Console
import typer

from uptop import __version__
from uptop.config import Config, load_config

# Create the main Typer app
app = typer.Typer(
    name="uptop",
    help="Universal Performance & Telemetry Output - A modern CLI+TUI system monitor",
    no_args_is_help=False,
    add_completion=True,
    rich_markup_mode="rich",
)

# Console for rich output
console = Console()


class OutputFormat(str, Enum):
    """Output format options for CLI mode."""

    JSON = "json"
    MARKDOWN = "markdown"
    PROMETHEUS = "prometheus"


class OutputMode(str, Enum):
    """Output mode options for CLI mode."""

    ONCE = "once"
    STREAM = "stream"
    CONTINUOUS = "continuous"


class Theme(str, Enum):
    """Available TUI themes."""

    DARK = "dark"
    LIGHT = "light"
    SOLARIZED = "solarized"
    NORD = "nord"
    GRUVBOX = "gruvbox"


def version_callback(value: bool) -> None:
    """Display version and exit."""
    if value:
        console.print(f"uptop version {__version__}")
        raise typer.Exit()


class PluginValidationResult:
    """Result of validating a single plugin."""

    def __init__(
        self,
        name: str,
        version: str,
        valid: bool,
        errors: list[str] | None = None,
    ) -> None:
        """Initialize validation result.

        Args:
            name: Plugin name
            version: Plugin version
            valid: Whether the plugin passed validation
            errors: List of validation error messages
        """
        self.name = name
        self.version = version
        self.valid = valid
        self.errors = errors or []


def validate_plugin(
    plugin: Any,
    plugin_name: str,
) -> PluginValidationResult:
    """Validate a single plugin for compatibility and correctness.

    Checks:
    - API version compatibility
    - Required methods exist
    - Schema is a valid Pydantic model (for pane plugins)

    Args:
        plugin: The plugin instance to validate
        plugin_name: Name of the plugin for error reporting

    Returns:
        PluginValidationResult with validation status and any errors
    """
    from uptop.plugin_api.base import (
        API_VERSION,
        ActionPlugin,
        CollectorPlugin,
        FormatterPlugin,
        PanePlugin,
    )

    errors: list[str] = []
    version = getattr(plugin, "version", "unknown")

    # Check API version compatibility
    plugin_api_version = getattr(plugin, "api_version", None)
    if plugin_api_version:
        try:
            plugin_major = int(plugin_api_version.split(".")[0])
            current_major = int(API_VERSION.split(".")[0])
            if plugin_major != current_major:
                errors.append(
                    f"Incompatible API version {plugin_api_version} "
                    f"(expected {API_VERSION})"
                )
        except (ValueError, IndexError):
            errors.append(f"Invalid API version format: {plugin_api_version}")

    # Check required methods based on plugin type
    if isinstance(plugin, PanePlugin):
        # Check collect_data method
        if not hasattr(plugin, "collect_data") or not callable(
            getattr(plugin, "collect_data", None)
        ):
            errors.append("Missing collect_data method")

        # Check render_tui method
        if not hasattr(plugin, "render_tui") or not callable(
            getattr(plugin, "render_tui", None)
        ):
            errors.append("Missing render_tui method")

        # Check get_schema method and validate it returns a Pydantic model
        if not hasattr(plugin, "get_schema") or not callable(
            getattr(plugin, "get_schema", None)
        ):
            errors.append("Missing get_schema method")
        else:
            try:
                schema = plugin.get_schema()
                if schema is not None and not (
                    isinstance(schema, type) and issubclass(schema, BaseModel)
                ):
                    errors.append("get_schema must return a Pydantic BaseModel subclass")
            except Exception as e:
                errors.append(f"get_schema raised error: {e}")

    elif isinstance(plugin, CollectorPlugin):
        if not hasattr(plugin, "collect") or not callable(
            getattr(plugin, "collect", None)
        ):
            errors.append("Missing collect method")

    elif isinstance(plugin, FormatterPlugin):
        if not hasattr(plugin, "format") or not callable(
            getattr(plugin, "format", None)
        ):
            errors.append("Missing format method")

    elif isinstance(plugin, ActionPlugin):
        if not hasattr(plugin, "can_execute") or not callable(
            getattr(plugin, "can_execute", None)
        ):
            errors.append("Missing can_execute method")
        if not hasattr(plugin, "execute") or not callable(
            getattr(plugin, "execute", None)
        ):
            errors.append("Missing execute method")

    return PluginValidationResult(
        name=plugin_name,
        version=version,
        valid=len(errors) == 0,
        errors=errors,
    )


def check_plugins_callback(value: bool) -> None:
    """Check all registered plugins for validity and exit.

    Loads all plugins from the registry and validates each one for:
    - API version compatibility
    - Required methods
    - Valid schema (for pane plugins)

    Outputs a summary of validation results.
    """
    if not value:
        return

    from uptop.plugins.registry import PluginRegistry

    console.print("[bold]Checking plugins...[/bold]\n")

    # Create registry and discover plugins
    registry = PluginRegistry()
    try:
        registry.discover_all(strict=False)
    except Exception as e:
        console.print(f"[red]Error during plugin discovery:[/red] {e}")
        raise typer.Exit(1) from e

    results: list[PluginValidationResult] = []
    valid_count = 0
    invalid_count = 0

    # Also check for failed plugins during discovery
    failed_plugins = registry.failed_plugins
    for plugin_name, error_msg in failed_plugins.items():
        results.append(
            PluginValidationResult(
                name=plugin_name,
                version="unknown",
                valid=False,
                errors=[f"Failed to load: {error_msg}"],
            )
        )
        invalid_count += 1

    # Validate each successfully loaded plugin
    for plugin_name in registry:
        try:
            plugin = registry.get(plugin_name)
            result = validate_plugin(plugin, plugin_name)
            results.append(result)
            if result.valid:
                valid_count += 1
            else:
                invalid_count += 1
        except Exception as e:
            results.append(
                PluginValidationResult(
                    name=plugin_name,
                    version="unknown",
                    valid=False,
                    errors=[f"Validation error: {e}"],
                )
            )
            invalid_count += 1

    # Sort results: valid first, then invalid
    results.sort(key=lambda r: (not r.valid, r.name))

    # Display results
    for result in results:
        if result.valid:
            console.print(
                f"[green]\u2713[/green] {result.name} (v{result.version}) - OK"
            )
        else:
            error_detail = result.errors[0] if result.errors else "Unknown error"
            console.print(
                f"[red]\u2717[/red] {result.name} (v{result.version}) - {error_detail}"
            )
            # Show additional errors if any
            for error in result.errors[1:]:
                console.print(f"    [dim]{error}[/dim]")

    # Summary
    total = valid_count + invalid_count
    console.print()
    if invalid_count == 0:
        console.print(
            f"[green]{total} plugins checked, all valid[/green]"
        )
    else:
        console.print(
            f"{total} plugins checked, "
            f"[green]{valid_count} valid[/green], "
            f"[red]{invalid_count} invalid[/red]"
        )

    # Exit with error code if any plugins are invalid
    raise typer.Exit(1 if invalid_count > 0 else 0)


def detect_mode(
    explicit_mode: str | None,
    format_specified: bool,
    stream_specified: bool,
) -> str:
    """Detect whether to run in TUI or CLI mode.

    Mode detection logic:
    1. If explicit mode specified (tui/cli command), use that
    2. If format flags present (--json, --markdown, etc.), use CLI mode
    3. If stream flags present (--stream, --continuous), use CLI mode
    4. If stdin is a TTY, use TUI mode
    5. Otherwise, use CLI mode

    Args:
        explicit_mode: Explicitly specified mode from command
        format_specified: Whether a format flag was provided
        stream_specified: Whether a stream mode flag was provided

    Returns:
        "tui" or "cli"
    """
    if explicit_mode:
        return explicit_mode

    if format_specified or stream_specified:
        return "cli"

    if sys.stdin.isatty() and sys.stdout.isatty():
        return "tui"

    return "cli"


def build_cli_overrides(
    interval: float | None = None,
    panes: list[str] | None = None,
    theme: Theme | None = None,
    layout: str | None = None,
    no_mouse: bool = False,
    format_: OutputFormat | None = None,
    output_mode: OutputMode | None = None,
    pretty: bool | None = None,
) -> dict[str, Any]:
    """Build config override dict from CLI flags.

    Args:
        interval: Refresh interval override
        panes: List of panes to show
        theme: TUI theme override
        layout: Layout preset name
        no_mouse: Disable mouse support
        format_: Output format for CLI mode
        output_mode: Output mode for CLI mode
        pretty: Pretty-print output

    Returns:
        Dictionary of config overrides
    """
    overrides: dict[str, Any] = {}

    if interval is not None:
        overrides["interval"] = interval

    # TUI overrides
    tui_overrides: dict[str, Any] = {}
    if theme is not None:
        tui_overrides["theme"] = theme.value
    if no_mouse:
        tui_overrides["mouse_enabled"] = False
    if layout is not None:
        if "layouts" not in tui_overrides:
            tui_overrides["layouts"] = {}
        tui_overrides["layouts"]["default"] = layout
    if panes is not None:
        # Set all panes to disabled, then enable specified ones
        tui_overrides["panes"] = {}
        for pane in panes:
            tui_overrides["panes"][pane] = {"enabled": True}

    if tui_overrides:
        overrides["tui"] = tui_overrides

    # CLI overrides
    cli_overrides: dict[str, Any] = {}
    if format_ is not None:
        cli_overrides["default_format"] = format_.value
    if output_mode is not None:
        cli_overrides["default_output_mode"] = output_mode.value
    if pretty is not None:
        cli_overrides["pretty_print"] = pretty

    if cli_overrides:
        overrides["cli"] = cli_overrides

    return overrides


# Common options
ConfigOption = Annotated[
    Path | None,
    typer.Option(
        "--config",
        "-c",
        help="Path to custom config file",
        envvar="UPTOP_CONFIG_PATH",
        exists=False,  # We handle existence check ourselves
    ),
]

IntervalOption = Annotated[
    float | None,
    typer.Option(
        "--interval",
        "-i",
        help="Refresh interval in seconds",
        min=0.1,
        max=3600,
    ),
]

PanesOption = Annotated[
    list[str] | None,
    typer.Option(
        "--panes",
        "-p",
        help="Comma-separated list of panes to show",
    ),
]

# TUI-specific options
ThemeOption = Annotated[
    Theme | None,
    typer.Option(
        "--theme",
        "-t",
        help="TUI color theme",
    ),
]

LayoutOption = Annotated[
    str | None,
    typer.Option(
        "--layout",
        "-l",
        help="Layout preset name",
    ),
]

NoMouseOption = Annotated[
    bool,
    typer.Option(
        "--no-mouse",
        help="Disable mouse support in TUI",
    ),
]

# CLI-specific options
JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        "-j",
        help="Output in JSON format (implies CLI mode)",
    ),
]

MarkdownOption = Annotated[
    bool,
    typer.Option(
        "--markdown",
        "-m",
        help="Output in Markdown format (implies CLI mode)",
    ),
]

PrometheusOption = Annotated[
    bool,
    typer.Option(
        "--prometheus",
        help="Output in Prometheus format (implies CLI mode)",
    ),
]

StreamOption = Annotated[
    bool,
    typer.Option(
        "--stream",
        "-s",
        help="Stream output continuously (implies CLI mode)",
    ),
]

OnceOption = Annotated[
    bool,
    typer.Option(
        "--once",
        "-o",
        help="Output once and exit (implies CLI mode)",
    ),
]

ContinuousOption = Annotated[
    bool,
    typer.Option(
        "--continuous",
        help="Output continuously, overwriting previous (implies CLI mode)",
    ),
]

PrettyOption = Annotated[
    bool | None,
    typer.Option(
        "--pretty/--no-pretty",
        help="Pretty-print output (default: True)",
    ),
]

QueryOption = Annotated[
    str | None,
    typer.Option(
        "--query",
        "-q",
        help="JMESPath query to filter output",
    ),
]

VersionOption = Annotated[
    bool | None,
    typer.Option(
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
]

CheckPluginsOption = Annotated[
    bool | None,
    typer.Option(
        "--check-plugins",
        callback=check_plugins_callback,
        is_eager=True,
        help="Validate all registered plugins and exit",
    ),
]

DebugOption = Annotated[
    bool,
    typer.Option(
        "--debug",
        help="Enable performance profiling and debug output",
    ),
]


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: ConfigOption = None,
    interval: IntervalOption = None,
    panes: PanesOption = None,
    theme: ThemeOption = None,
    layout: LayoutOption = None,
    no_mouse: NoMouseOption = False,
    json_format: JsonOption = False,
    markdown_format: MarkdownOption = False,
    prometheus_format: PrometheusOption = False,
    stream: StreamOption = False,
    once: OnceOption = False,
    continuous: ContinuousOption = False,
    pretty: PrettyOption = None,
    query: QueryOption = None,
    version: VersionOption = None,
    check_plugins: CheckPluginsOption = None,
    debug: DebugOption = False,
) -> None:
    """uptop - Universal Performance & Telemetry Output.

    A modern CLI+TUI system monitor with plugin architecture.

    By default, runs in TUI mode if connected to a terminal.
    Use format flags (--json, --markdown, --prometheus) for CLI mode output.

    Examples:

        uptop                          Start interactive TUI monitor

        uptop --json --once            Output system metrics as JSON once

        uptop --prometheus --stream    Stream metrics in Prometheus format

        uptop --check-plugins          Validate all registered plugins
    """
    # Only run if no subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    # Determine output format
    output_format: OutputFormat | None = None
    if json_format:
        output_format = OutputFormat.JSON
    elif markdown_format:
        output_format = OutputFormat.MARKDOWN
    elif prometheus_format:
        output_format = OutputFormat.PROMETHEUS

    # Determine output mode
    output_mode: OutputMode | None = None
    if stream:
        output_mode = OutputMode.STREAM
    elif once:
        output_mode = OutputMode.ONCE
    elif continuous:
        output_mode = OutputMode.CONTINUOUS

    # Detect mode
    format_specified = output_format is not None
    stream_specified = output_mode is not None
    mode = detect_mode(None, format_specified, stream_specified)

    # Build CLI overrides
    overrides = build_cli_overrides(
        interval=interval,
        panes=panes,
        theme=theme,
        layout=layout,
        no_mouse=no_mouse,
        format_=output_format,
        output_mode=output_mode,
        pretty=pretty,
    )

    # Set default mode based on detection
    overrides["default_mode"] = mode

    # Load configuration
    try:
        config_path = str(config) if config else None
        cfg = load_config(config_path=config_path, cli_overrides=overrides)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from e

    # Parse pane names
    pane_names = parse_panes_option(panes)

    # Run the appropriate mode
    run_uptop(cfg, query=query, pane_names=pane_names, debug_mode=debug)


@app.command("tui")
def tui_command(
    config: ConfigOption = None,
    interval: IntervalOption = None,
    panes: PanesOption = None,
    theme: ThemeOption = None,
    layout: LayoutOption = None,
    no_mouse: NoMouseOption = False,
    debug: DebugOption = False,
) -> None:
    """Run uptop in TUI (Terminal User Interface) mode.

    This is the default mode when running in an interactive terminal.
    """
    overrides = build_cli_overrides(
        interval=interval,
        panes=panes,
        theme=theme,
        layout=layout,
        no_mouse=no_mouse,
    )
    overrides["default_mode"] = "tui"

    try:
        config_path = str(config) if config else None
        cfg = load_config(config_path=config_path, cli_overrides=overrides)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from e

    run_uptop(cfg, debug_mode=debug)


@app.command("cli")
def cli_command(
    config: ConfigOption = None,
    interval: IntervalOption = None,
    panes: PanesOption = None,
    json_format: JsonOption = False,
    markdown_format: MarkdownOption = False,
    prometheus_format: PrometheusOption = False,
    stream: StreamOption = False,
    once: OnceOption = False,
    continuous: ContinuousOption = False,
    pretty: PrettyOption = None,
    query: QueryOption = None,
) -> None:
    """Run uptop in CLI mode with structured output.

    Outputs system metrics in the specified format (JSON, Markdown, or Prometheus).
    """
    # Determine output format
    output_format: OutputFormat | None = None
    if json_format:
        output_format = OutputFormat.JSON
    elif markdown_format:
        output_format = OutputFormat.MARKDOWN
    elif prometheus_format:
        output_format = OutputFormat.PROMETHEUS

    # Determine output mode
    output_mode: OutputMode | None = None
    if stream:
        output_mode = OutputMode.STREAM
    elif once:
        output_mode = OutputMode.ONCE
    elif continuous:
        output_mode = OutputMode.CONTINUOUS

    overrides = build_cli_overrides(
        interval=interval,
        panes=panes,
        format_=output_format,
        output_mode=output_mode,
        pretty=pretty,
    )
    overrides["default_mode"] = "cli"

    try:
        config_path = str(config) if config else None
        cfg = load_config(config_path=config_path, cli_overrides=overrides)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from e

    # Parse pane names for CLI mode
    pane_names = parse_panes_option(panes)

    run_uptop(cfg, query=query, pane_names=pane_names)


@app.command("serve")
def serve_command(
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port to serve on",
        ),
    ] = 8000,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            "-H",
            help="Host to bind to",
        ),
    ] = "localhost",
) -> None:
    """Serve uptop as a web application."""
    from textual_serve.server import Server

    server = Server(f"{sys.argv[0]} tui", host=host, port=port, title="uptop")
    server.serve()


def parse_panes_option(panes: list[str] | None) -> list[str] | None:
    """Parse the --panes option into a list of pane names.

    Handles both repeated --panes flags and comma-separated values.

    Args:
        panes: List from typer, may contain comma-separated values

    Returns:
        Flattened list of pane names, or None if no panes specified
    """
    if not panes:
        return None

    result: list[str] = []
    for item in panes:
        # Split by comma and strip whitespace
        for name in item.split(","):
            name = name.strip()
            if name:
                result.append(name)

    return result if result else None


def run_uptop(
    config: Config,
    query: str | None = None,
    pane_names: list[str] | None = None,
    debug_mode: bool = False,
) -> None:
    """Run uptop with the given configuration.

    Launches either the TUI or CLI mode based on configuration.

    Args:
        config: Validated configuration object
        query: Optional JMESPath query for filtering output (CLI mode only)
        pane_names: Optional list of pane names to collect (CLI mode only)
        debug_mode: Enable performance profiling and debug output
    """
    mode = config.default_mode

    if mode == "tui":
        # Import here to avoid loading Textual when not needed
        from uptop.tui import run_app

        run_app(config, debug_mode=debug_mode)
    else:
        # CLI mode - use the CLI runner
        from uptop.cli_runner import run_cli_mode

        format_name = config.cli.default_format
        output_mode = config.cli.default_output_mode
        once = output_mode == "once"
        stream = output_mode == "stream"

        exit_code = run_cli_mode(
            format_name=format_name,
            pane_names=pane_names,
            once=once,
            stream=stream,
            config=config,
        )

        if exit_code != 0:
            raise typer.Exit(exit_code)


def cli_main() -> None:
    """Entry point for the CLI application."""
    app()
