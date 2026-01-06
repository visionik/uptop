"""Sentry SDK integration for uptop.

This module provides:
- Sentry initialization with asyncio support
- Manual profiling for plugin execution
- Logging integration (logs forwarded to Sentry)
- Metrics (counters, gauges, distributions)
- Context, tags, and extras helpers
- System information capture
- Error tracking utilities

Usage:
    from uptop.sentry import init_sentry, set_uptop_context, start_profiler, stop_profiler
    from uptop.sentry import log_info, log_warning, log_error
    from uptop.sentry import metric_count, metric_gauge, metric_distribution

    init_sentry()  # Call at startup
    set_uptop_context(mode="tui", panes=["cpu", "memory"])  # Add context

    # Logging
    log_info("Application started")
    log_warning("Plugin slow", plugin="cpu", duration_ms=150)
    log_error("Plugin failed", plugin="gpu", error="timeout")

    # Metrics
    metric_count("plugin.refresh", 1, tags={"plugin": "cpu"})
    metric_gauge("pane.count", 5)
    metric_distribution("plugin.duration_ms", 42.5, tags={"plugin": "memory"})

    # Profile plugin execution
    start_profiler()
    result = plugin.collect_data()
    stop_profiler()
"""

from __future__ import annotations

from collections.abc import Generator
import contextlib
import logging
import os
import platform
import sys
from typing import Any

import sentry_sdk
from sentry_sdk import metrics
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from uptop import __version__

# Sentry DSN for uptop
SENTRY_DSN = "https://e6687b7593c0963df3f499a54bb80bd9@o4510618809270272.ingest.us.sentry.io/4510618812022784"


def init_sentry(
    *,
    dsn: str | None = None,
    traces_sample_rate: float = 1.0,
    profile_session_sample_rate: float = 1.0,
    debug: bool = False,
    event_level: int | None = None,
) -> None:
    """Initialize Sentry SDK with uptop-specific configuration.

    Configures Sentry with:
    - AsyncioIntegration for async task error capture
    - LoggingIntegration for capturing log messages
    - Manual profiling lifecycle for plugin profiling
    - System context (OS, Python version, architecture)
    - Default tags for filtering

    Args:
        dsn: Sentry DSN (uses default if not provided)
        traces_sample_rate: Sample rate for performance traces (0.0-1.0)
        profile_session_sample_rate: Sample rate for continuous profiling (0.0-1.0)
        debug: Enable Sentry debug mode for troubleshooting
        event_level: Minimum log level to create Sentry events (default: ERROR in prod, WARNING in dev)
    """
    # Determine event level based on environment or explicit parameter
    if event_level is None:
        # Use WARNING in development (detected by UPTOP_ENV or debug flag)
        # Use ERROR in production
        is_development = (
            os.environ.get("UPTOP_ENV", "").lower() in ("dev", "development")
            or debug
            or __version__.endswith("-dev")
            or "0.1." in __version__  # Early development versions
        )
        event_level = logging.WARNING if is_development else logging.ERROR

    sentry_sdk.init(
        dsn=dsn or SENTRY_DSN,
        traces_sample_rate=traces_sample_rate,
        profile_session_sample_rate=profile_session_sample_rate,
        profile_lifecycle="manual",  # Manual control via start_profiler/stop_profiler
        debug=debug,
        send_default_pii=False,  # Don't send personally identifiable info
        enable_tracing=True,
        environment=os.environ.get("UPTOP_ENV", "production"),
        _experiments={
            "enable_logs": True,  # Enable Sentry logs
        },
        integrations=[
            AsyncioIntegration(),
            LoggingIntegration(
                level=logging.INFO,  # Capture INFO+ as breadcrumbs
                event_level=event_level,  # Create events based on environment
            ),
        ],
        # Before send hook to add extra context
        before_send=_before_send,
    )

    # Set initial tags
    sentry_sdk.set_tag("app.version", __version__)
    sentry_sdk.set_tag("python.version", platform.python_version())
    sentry_sdk.set_tag("os.name", platform.system())
    sentry_sdk.set_tag("os.version", platform.release())
    sentry_sdk.set_tag("arch", platform.machine())

    # Set system context
    set_system_context()


def _before_send(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any] | None:
    """Process events before sending to Sentry.

    Args:
        event: The event dictionary
        hint: Additional context about the event

    Returns:
        The event to send, or None to drop it
    """
    # Add current working directory
    event.setdefault("extra", {})["cwd"] = os.getcwd()

    # You can filter out certain errors here if needed
    # For example, to ignore KeyboardInterrupt:
    if "exc_info" in hint:
        exc_type, _, _ = hint["exc_info"]
        if exc_type is KeyboardInterrupt:
            return None

    return event


def set_system_context() -> None:
    """Set system-level context for all events.

    Captures:
    - OS information
    - Python runtime details
    - CPU architecture
    - Terminal information
    """
    sentry_sdk.set_context("system", {
        "os": platform.system(),
        "os_version": platform.release(),
        "os_full": platform.platform(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "unknown",
        "terminal": os.environ.get("TERM", "unknown"),
        "shell": os.environ.get("SHELL", "unknown"),
        "is_tty": sys.stdout.isatty(),
    })


def set_uptop_context(
    *,
    mode: str | None = None,
    panes: list[str] | None = None,
    config_path: str | None = None,
    debug_mode: bool = False,
) -> None:
    """Set uptop-specific context for error tracking.

    Args:
        mode: Current mode (tui/cli)
        panes: List of active panes
        config_path: Path to config file if custom
        debug_mode: Whether debug mode is enabled
    """
    context: dict[str, Any] = {}

    if mode is not None:
        context["mode"] = mode
        sentry_sdk.set_tag("uptop.mode", mode)

    if panes is not None:
        context["panes"] = panes
        context["pane_count"] = len(panes)

    if config_path is not None:
        context["config_path"] = config_path
        sentry_sdk.set_tag("uptop.custom_config", "true")

    context["debug_mode"] = debug_mode
    if debug_mode:
        sentry_sdk.set_tag("uptop.debug", "true")

    if context:
        sentry_sdk.set_context("uptop", context)


def set_gpu_context(
    *,
    platform_name: str,
    gpu_name: str | None = None,
    gpu_cores: int | None = None,
    powermetrics_available: bool = False,
) -> None:
    """Set GPU-specific context.

    Args:
        platform_name: GPU platform (apple_silicon, nvidia, amd, etc.)
        gpu_name: GPU model name
        gpu_cores: Number of GPU cores
        powermetrics_available: Whether powermetrics is accessible
    """
    context: dict[str, Any] = {
        "platform": platform_name,
        "powermetrics_available": powermetrics_available,
    }

    if gpu_name:
        context["name"] = gpu_name
        sentry_sdk.set_tag("gpu.name", gpu_name)

    if gpu_cores:
        context["cores"] = gpu_cores

    sentry_sdk.set_tag("gpu.platform", platform_name)
    sentry_sdk.set_context("gpu", context)


def capture_collector_error(
    collector_name: str,
    error: Exception,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """Capture an error from a data collector with context.

    Args:
        collector_name: Name of the collector that failed
        error: The exception that occurred
        extra: Additional context to include
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("collector", collector_name)
        scope.set_context("collector_error", {
            "collector": collector_name,
            "error_type": type(error).__name__,
            **(extra or {}),
        })
        sentry_sdk.capture_exception(error)


def capture_plugin_error(
    plugin_name: str,
    plugin_type: str,
    error: Exception,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """Capture an error from a plugin with context.

    Args:
        plugin_name: Name of the plugin that failed
        plugin_type: Type of plugin (pane, collector, formatter, action)
        error: The exception that occurred
        extra: Additional context to include
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("plugin.name", plugin_name)
        scope.set_tag("plugin.type", plugin_type)
        scope.set_context("plugin_error", {
            "plugin": plugin_name,
            "type": plugin_type,
            "error_type": type(error).__name__,
            **(extra or {}),
        })
        sentry_sdk.capture_exception(error)


def add_breadcrumb(
    message: str,
    category: str = "uptop",
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """Add a breadcrumb for debugging.

    Breadcrumbs are trail of events leading up to an error.

    Args:
        message: Description of the event
        category: Category for grouping (e.g., "ui", "collector", "config")
        level: Severity level (debug, info, warning, error)
        data: Additional data to attach
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data,
    )


def start_transaction(
    name: str,
    op: str = "task",
) -> Any:
    """Start a performance transaction.

    Args:
        name: Transaction name
        op: Operation type (task, http, db, etc.)

    Returns:
        Transaction context manager
    """
    return sentry_sdk.start_transaction(name=name, op=op)


def start_profiler() -> None:
    """Start the Sentry profiler.

    Call this before executing plugin code to capture profiling data.
    Must be paired with a call to stop_profiler().
    """
    sentry_sdk.profiler.start_profiler()


def stop_profiler() -> None:
    """Stop the Sentry profiler.

    Call this after plugin code completes to finalize profiling data.
    Must be paired with a prior call to start_profiler().
    """
    sentry_sdk.profiler.stop_profiler()


@contextlib.contextmanager
def profile_plugin(plugin_name: str) -> Generator[None, None, None]:
    """Context manager to profile plugin execution.

    Wraps plugin execution with start_profiler/stop_profiler calls
    and adds a breadcrumb for the plugin execution.

    Args:
        plugin_name: Name of the plugin being profiled

    Yields:
        None

    Example:
        with profile_plugin("cpu"):
            data = cpu_plugin.collect_data()
    """
    add_breadcrumb(
        f"Starting plugin: {plugin_name}",
        category="plugin",
        level="debug",
        data={"plugin": plugin_name},
    )
    start_profiler()
    try:
        yield
    finally:
        stop_profiler()
        add_breadcrumb(
            f"Completed plugin: {plugin_name}",
            category="plugin",
            level="debug",
            data={"plugin": plugin_name},
        )


# =============================================================================
# Logging Functions
# =============================================================================


def log_debug(message: str, **kwargs: Any) -> None:
    """Log a debug message to Sentry.

    Args:
        message: Log message
        **kwargs: Additional context as key-value pairs
    """
    sentry_sdk.logger.debug(message, extra=kwargs)


def log_info(message: str, **kwargs: Any) -> None:
    """Log an info message to Sentry.

    Args:
        message: Log message
        **kwargs: Additional context as key-value pairs
    """
    sentry_sdk.logger.info(message, extra=kwargs)


def log_warning(message: str, **kwargs: Any) -> None:
    """Log a warning message to Sentry.

    Args:
        message: Log message
        **kwargs: Additional context as key-value pairs
    """
    sentry_sdk.logger.warning(message, extra=kwargs)


def log_error(message: str, **kwargs: Any) -> None:
    """Log an error message to Sentry.

    Args:
        message: Log message
        **kwargs: Additional context as key-value pairs
    """
    sentry_sdk.logger.error(message, extra=kwargs)


# =============================================================================
# Metrics Functions
# =============================================================================


def metric_count(
    key: str,
    value: int = 1,
    *,
    tags: dict[str, str] | None = None,
) -> None:
    """Increment a counter metric.

    Use for counting occurrences (e.g., plugin refreshes, errors).

    Args:
        key: Metric name (e.g., "plugin.refresh")
        value: Amount to increment (default: 1)
        tags: Optional tags for filtering/grouping
    """
    metrics.count(key, value, attributes=tags)


def metric_gauge(
    key: str,
    value: float,
    *,
    tags: dict[str, str] | None = None,
) -> None:
    """Set a gauge metric.

    Use for current values (e.g., active panes, memory usage).

    Args:
        key: Metric name (e.g., "pane.active_count")
        value: Current value
        tags: Optional tags for filtering/grouping
    """
    metrics.gauge(key, value, attributes=tags)


def metric_distribution(
    key: str,
    value: float,
    *,
    unit: str = "millisecond",
    tags: dict[str, str] | None = None,
) -> None:
    """Record a distribution metric.

    Use for measuring durations or sizes (e.g., plugin execution time).

    Args:
        key: Metric name (e.g., "plugin.collect_duration")
        value: Measured value
        unit: Unit of measurement (default: "millisecond")
        tags: Optional tags for filtering/grouping
    """
    metrics.distribution(key, value, unit=unit, attributes=tags)


@contextlib.contextmanager
def metric_timing(
    key: str,
    *,
    tags: dict[str, str] | None = None,
) -> Generator[None, None, None]:
    """Context manager to measure execution time.

    Args:
        key: Metric name for the timing
        tags: Optional tags for filtering/grouping

    Yields:
        None

    Example:
        with metric_timing("plugin.collect", tags={"plugin": "cpu"}):
            data = await plugin.collect_data()
    """
    import time

    start = time.monotonic()
    try:
        yield
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        metric_distribution(key, duration_ms, tags=tags)


# =============================================================================
# Span/Tracing Functions
# =============================================================================


def start_span(
    name: str,
    op: str = "function",
    **attributes: Any,
) -> Any:
    """Start a new span for tracing.

    Args:
        name: Span name (e.g., "collect_cpu_data")
        op: Operation type (e.g., "plugin.collect", "plugin.render")
        **attributes: Additional attributes to attach

    Returns:
        Span context manager

    Example:
        with start_span("collect_data", op="plugin.collect", plugin="cpu"):
            data = await plugin.collect_data()
    """
    span = sentry_sdk.start_span(name=name, op=op)
    for key, value in attributes.items():
        span.set_data(key, value)
    return span


def start_transaction_span(
    name: str,
    op: str = "task",
    **attributes: Any,
) -> Any:
    """Start a new transaction (top-level span).

    Use for major operations like a full refresh cycle.

    Args:
        name: Transaction name (e.g., "refresh_cycle")
        op: Operation type (e.g., "task", "http")
        **attributes: Additional attributes to attach

    Returns:
        Transaction context manager

    Example:
        with start_transaction_span("refresh_cycle", pane_count=5):
            for pane in panes:
                refresh_pane(pane)
    """
    transaction = sentry_sdk.start_transaction(name=name, op=op)
    for key, value in attributes.items():
        transaction.set_data(key, value)
    return transaction


@contextlib.contextmanager
def trace_plugin_collect(plugin_name: str) -> Generator[None, None, None]:
    """Context manager to trace a plugin data collection.

    Creates a span with timing, profiling, and metrics.

    Args:
        plugin_name: Name of the plugin

    Yields:
        None

    Example:
        with trace_plugin_collect("cpu"):
            data = await cpu_plugin.collect_data()
    """
    import time

    with sentry_sdk.start_span(
        name=f"collect:{plugin_name}",
        op="plugin.collect",
    ) as span:
        span.set_data("plugin", plugin_name)
        start_time = time.monotonic()
        start_profiler()
        try:
            yield
            span.set_data("success", True)
        except Exception as e:
            span.set_data("success", False)
            span.set_data("error", str(e))
            raise
        finally:
            stop_profiler()
            duration_ms = (time.monotonic() - start_time) * 1000
            span.set_data("duration_ms", duration_ms)
            record_plugin_collect(
                plugin_name,
                duration_ms,
                success=span._data.get("success", False),
            )


@contextlib.contextmanager
def trace_plugin_render(plugin_name: str) -> Generator[None, None, None]:
    """Context manager to trace a plugin render operation.

    Creates a span with timing and metrics.

    Args:
        plugin_name: Name of the plugin

    Yields:
        None

    Example:
        with trace_plugin_render("cpu"):
            widget = cpu_plugin.render_tui(data)
    """
    import time

    with sentry_sdk.start_span(
        name=f"render:{plugin_name}",
        op="plugin.render",
    ) as span:
        span.set_data("plugin", plugin_name)
        start_time = time.monotonic()
        try:
            yield
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            span.set_data("duration_ms", duration_ms)
            record_plugin_render(plugin_name, duration_ms)


@contextlib.contextmanager
def trace_refresh_cycle(pane_names: list[str]) -> Generator[None, None, None]:
    """Context manager to trace a complete refresh cycle.

    Creates a transaction that encompasses all plugin refreshes.

    Args:
        pane_names: List of pane names being refreshed

    Yields:
        None

    Example:
        with trace_refresh_cycle(["cpu", "memory", "gpu"]):
            for pane in panes:
                await refresh_pane(pane)
    """
    import time

    with sentry_sdk.start_transaction(
        name="refresh_cycle",
        op="tui.refresh",
    ) as transaction:
        transaction.set_data("pane_count", len(pane_names))
        transaction.set_data("panes", pane_names)
        start_time = time.monotonic()
        try:
            yield
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            transaction.set_data("duration_ms", duration_ms)
            record_refresh_cycle(duration_ms, len(pane_names))


# =============================================================================
# Convenience Functions for Plugin Instrumentation
# =============================================================================


def record_plugin_collect(
    plugin_name: str,
    duration_ms: float,
    success: bool = True,
) -> None:
    """Record metrics for a plugin data collection.

    Args:
        plugin_name: Name of the plugin
        duration_ms: Time taken in milliseconds
        success: Whether collection succeeded
    """
    tags = {"plugin": plugin_name, "success": str(success).lower()}

    metric_count("plugin.collect.total", 1, tags=tags)
    metric_distribution("plugin.collect.duration_ms", duration_ms, tags=tags)

    if not success:
        metric_count("plugin.collect.errors", 1, tags={"plugin": plugin_name})


def record_plugin_render(
    plugin_name: str,
    duration_ms: float,
) -> None:
    """Record metrics for a plugin render operation.

    Args:
        plugin_name: Name of the plugin
        duration_ms: Time taken in milliseconds
    """
    tags = {"plugin": plugin_name}
    metric_count("plugin.render.total", 1, tags=tags)
    metric_distribution("plugin.render.duration_ms", duration_ms, tags=tags)


def record_app_start(mode: str, pane_count: int) -> None:
    """Record app startup metrics.

    Args:
        mode: Application mode (tui/cli)
        pane_count: Number of active panes
    """
    log_info("uptop started", mode=mode, pane_count=pane_count)
    metric_count("app.start", 1, tags={"mode": mode})
    metric_gauge("app.pane_count", pane_count, tags={"mode": mode})


def record_refresh_cycle(duration_ms: float, pane_count: int) -> None:
    """Record metrics for a complete refresh cycle.

    Args:
        duration_ms: Total time for refresh cycle
        pane_count: Number of panes refreshed
    """
    metric_count("refresh.cycle.total", 1)
    metric_distribution("refresh.cycle.duration_ms", duration_ms)
    metric_gauge("refresh.cycle.pane_count", pane_count)
