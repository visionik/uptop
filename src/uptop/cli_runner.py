"""CLI mode runner for uptop.

This module provides the implementation for CLI mode operations:
- Single snapshot collection (--once)
- Data collection from pane plugins
- Output formatting and printing

The runner coordinates between the plugin registry, pane plugins,
and formatters to produce CLI output.
"""

from __future__ import annotations

import asyncio
import socket
import sys
from datetime import UTC, datetime
from typing import Any

from rich.console import Console

from uptop.config import Config
from uptop.formatters import JsonFormatter, PrometheusFormatter
from uptop.models.base import MetricData, PluginType
from uptop.plugin_api.base import FormatterPlugin, PanePlugin
from uptop.plugins import PluginRegistry

console = Console(stderr=True)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


# Built-in pane plugins
BUILTIN_PANES: dict[str, type[PanePlugin]] = {}


def _load_builtin_panes() -> None:
    """Load built-in pane plugin classes."""
    global BUILTIN_PANES
    if BUILTIN_PANES:
        return

    # Import pane plugins
    from uptop.plugins.cpu import CPUPane
    from uptop.plugins.disk import DiskPane
    from uptop.plugins.memory import MemoryPane
    from uptop.plugins.network import NetworkPane
    from uptop.plugins.processes import ProcessPane

    BUILTIN_PANES = {
        "cpu": CPUPane,
        "memory": MemoryPane,
        "disk": DiskPane,
        "network": NetworkPane,
        "processes": ProcessPane,
    }


def get_formatter(format_name: str, config: Config) -> FormatterPlugin:
    """Get a formatter plugin by name.

    Args:
        format_name: The format name (json, prometheus)
        config: Application configuration

    Returns:
        Initialized formatter plugin

    Raises:
        ValueError: If format is not recognized
    """
    pretty_print = config.cli.pretty_print

    if format_name == "json":
        formatter = JsonFormatter(pretty_print=pretty_print)
        formatter.initialize({"pretty_print": pretty_print})
        return formatter
    elif format_name == "prometheus":
        formatter = PrometheusFormatter()
        formatter.initialize()
        return formatter
    else:
        raise ValueError(f"Unknown format: {format_name}. Available: json, prometheus")


def get_available_panes() -> list[str]:
    """Get list of available pane names.

    Returns:
        List of pane names that can be collected
    """
    _load_builtin_panes()
    return list(BUILTIN_PANES.keys())


def validate_pane_names(pane_names: list[str]) -> tuple[list[str], list[str]]:
    """Validate pane names against available panes.

    Args:
        pane_names: List of pane names to validate

    Returns:
        Tuple of (valid_panes, invalid_panes)
    """
    available = set(get_available_panes())
    valid = []
    invalid = []

    for name in pane_names:
        # Normalize name (lowercase, handle common aliases)
        normalized = name.lower().strip()

        # Handle common aliases
        aliases = {
            "mem": "memory",
            "proc": "processes",
            "procs": "processes",
            "process": "processes",
            "net": "network",
        }
        normalized = aliases.get(normalized, normalized)

        if normalized in available:
            valid.append(normalized)
        else:
            invalid.append(name)

    return valid, invalid


async def collect_pane_data(pane: PanePlugin, pane_name: str) -> tuple[str, MetricData | None]:
    """Collect data from a single pane.

    Args:
        pane: The pane plugin instance
        pane_name: Name of the pane for error reporting

    Returns:
        Tuple of (pane_name, data or None if collection failed)
    """
    try:
        data = await pane.collect_data()
        return pane_name, data
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to collect {pane_name} data: {e}[/yellow]")
        return pane_name, None


async def collect_all_panes(
    pane_names: list[str] | None = None,
    config: Config | None = None,
) -> dict[str, MetricData]:
    """Collect data from all specified panes.

    Args:
        pane_names: List of pane names to collect, or None for all
        config: Optional configuration for pane initialization

    Returns:
        Dictionary mapping pane names to their collected data
    """
    _load_builtin_panes()

    # Determine which panes to collect
    if pane_names is None:
        pane_names = list(BUILTIN_PANES.keys())

    # Create and initialize pane instances
    panes: list[tuple[str, PanePlugin]] = []
    for name in pane_names:
        if name not in BUILTIN_PANES:
            continue

        pane_class = BUILTIN_PANES[name]
        pane = pane_class()

        # Get pane-specific config
        pane_config: dict[str, Any] | None = None
        if config:
            pane_config = config.get_plugin_config(name)

        pane.initialize(pane_config)
        panes.append((name, pane))

    # Collect data from all panes concurrently
    tasks = [collect_pane_data(pane, name) for name, pane in panes]
    results = await asyncio.gather(*tasks)

    # Build result dictionary, filtering out None results
    data: dict[str, MetricData] = {}
    for name, result in results:
        if result is not None:
            data[name] = result

    # Shutdown panes
    for name, pane in panes:
        try:
            pane.shutdown()
        except Exception:
            pass

    return data


def build_snapshot(pane_data: dict[str, MetricData]) -> dict[str, Any]:
    """Build a complete snapshot dictionary from pane data.

    Args:
        pane_data: Dictionary of pane name -> MetricData

    Returns:
        Snapshot dictionary suitable for formatters
    """
    return {
        "timestamp": _utcnow(),
        "hostname": socket.gethostname(),
        "panes": pane_data,
    }


async def run_cli_once(
    format_name: str,
    pane_names: list[str] | None,
    config: Config,
) -> int:
    """Run a single CLI collection cycle.

    Args:
        format_name: Output format (json, prometheus)
        pane_names: List of pane names to collect, or None for all
        config: Application configuration

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Validate pane names if specified
    if pane_names:
        valid_panes, invalid_panes = validate_pane_names(pane_names)

        if invalid_panes:
            available = get_available_panes()
            console.print(
                f"[red]Error: Unknown pane(s): {', '.join(invalid_panes)}[/red]"
            )
            console.print(f"[yellow]Available panes: {', '.join(available)}[/yellow]")
            return 1

        pane_names = valid_panes

    # Get formatter
    try:
        formatter = get_formatter(format_name, config)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    # Collect data from panes
    try:
        pane_data = await collect_all_panes(pane_names, config)
    except Exception as e:
        console.print(f"[red]Error collecting data: {e}[/red]")
        return 1

    if not pane_data:
        console.print("[yellow]Warning: No data collected from any pane[/yellow]")
        return 1

    # Build snapshot and format output
    snapshot = build_snapshot(pane_data)
    output = formatter.format(snapshot)

    # Print to stdout
    print(output)

    return 0


async def run_cli_continuous(
    format_name: str,
    pane_names: list[str] | None,
    config: Config,
    stream: bool = False,
) -> int:
    """Run CLI in continuous/streaming mode.

    Continuously collects data and outputs at the configured interval.
    For --stream mode, outputs newline-delimited JSON (NDJSON).
    For --continuous mode, clears screen and overwrites previous output.

    Args:
        format_name: Output format (json, prometheus)
        pane_names: List of pane names to collect, or None for all
        config: Application configuration
        stream: If True, use streaming mode (NDJSON). If False, use continuous mode.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Validate pane names if specified
    if pane_names:
        valid_panes, invalid_panes = validate_pane_names(pane_names)

        if invalid_panes:
            available = get_available_panes()
            console.print(
                f"[red]Error: Unknown pane(s): {', '.join(invalid_panes)}[/red]"
            )
            console.print(f"[yellow]Available panes: {', '.join(available)}[/yellow]")
            return 1

        pane_names = valid_panes

    # Get formatter
    try:
        formatter = get_formatter(format_name, config)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    interval = config.interval if config else 1.0

    try:
        while True:
            # Collect data from panes
            try:
                pane_data = await collect_all_panes(pane_names, config)
            except Exception as e:
                console.print(f"[red]Error collecting data: {e}[/red]")
                await asyncio.sleep(interval)
                continue

            if pane_data:
                # Build snapshot and format output
                snapshot = build_snapshot(pane_data)
                output = formatter.format(snapshot)

                if stream:
                    # Streaming mode: just print each line (NDJSON for JSON format)
                    print(output, flush=True)
                else:
                    # Continuous mode: clear screen and overwrite
                    print("\033[2J\033[H", end="")  # Clear screen, move cursor to top
                    print(output, flush=True)

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        return 0

    return 0


def run_cli_mode(
    format_name: str = "json",
    pane_names: list[str] | None = None,
    once: bool = True,
    stream: bool = False,
    config: Config | None = None,
) -> int:
    """Run uptop in CLI mode.

    This is the main entry point for CLI mode operations.

    Args:
        format_name: Output format (json, prometheus)
        pane_names: List of pane names to collect, or None for all
        once: If True, collect once and exit
        stream: If True, use streaming mode (NDJSON output)
        config: Application configuration

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Load default config if not provided
    if config is None:
        from uptop.config import load_config
        config = load_config()

    if once:
        return asyncio.run(run_cli_once(format_name, pane_names, config))
    else:
        # Continuous or streaming mode
        try:
            return asyncio.run(run_cli_continuous(format_name, pane_names, config, stream=stream))
        except KeyboardInterrupt:
            # Graceful exit on Ctrl+C
            return 0
