"""CPU Pane Plugin for uptop.

This module provides the CPU monitoring pane which displays:
- Per-core CPU usage percentages
- CPU frequencies (current, min, max)
- Load averages (1, 5, 15 minutes)
- CPU temperatures (when available)

The plugin uses psutil for all data collection and handles gracefully
the case where certain metrics (like temperatures) may not be available
on all platforms.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

import psutil
from pydantic import BaseModel, ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import MetricData, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget


# Cache CPU count - it never changes during runtime
@lru_cache(maxsize=1)
def _get_cpu_count() -> int:
    """Get the number of logical CPU cores (cached)."""
    return psutil.cpu_count(logical=True) or 1


# Cache whether sensors_temperatures is available
@lru_cache(maxsize=1)
def _has_temperature_sensors() -> bool:
    """Check if temperature sensors are available (cached)."""
    return hasattr(psutil, "sensors_temperatures")


class CPUCore(BaseModel):
    """Data model for a single CPU core.

    Attributes:
        id: Core identifier (0-indexed)
        usage_percent: Current CPU usage as percentage (0-100) [gauge]
        freq_mhz: Current frequency in MHz (None if unavailable) [gauge]
        temp_celsius: Current temperature in Celsius (None if unavailable) [gauge]
    """

    # Use frozen=True for immutability and potential hash caching
    model_config = ConfigDict(frozen=True)

    id: int = Field(..., ge=0, description="Core identifier (0-indexed)")
    usage_percent: float = gauge_field("CPU usage percentage", ge=0.0, le=100.0)
    freq_mhz: float | None = gauge_field("Current frequency in MHz", default=None, ge=0.0)
    temp_celsius: float | None = gauge_field("Temperature in Celsius", default=None)


class CPUData(MetricData):
    """Aggregated CPU metrics for all cores.

    This is the data model returned by CPUCollector and consumed by CPUPane.

    Attributes:
        cores: List of per-core CPU data
        load_avg_1min: System load average over 1 minute [gauge]
        load_avg_5min: System load average over 5 minutes [gauge]
        load_avg_15min: System load average over 15 minutes [gauge]
    """

    cores: list[CPUCore] = Field(default_factory=list, description="Per-core CPU data")
    load_avg_1min: float = gauge_field("1-minute load average", default=0.0, ge=0.0)
    load_avg_5min: float = gauge_field("5-minute load average", default=0.0, ge=0.0)
    load_avg_15min: float = gauge_field("15-minute load average", default=0.0, ge=0.0)

    @property
    def total_usage_percent(self) -> float:
        """Calculate average CPU usage across all cores."""
        if not self.cores:
            return 0.0
        return sum(core.usage_percent for core in self.cores) / len(self.cores)

    @property
    def core_count(self) -> int:
        """Return the number of CPU cores."""
        return len(self.cores)


class CPUCollector(DataCollector[CPUData]):
    """Collector for CPU metrics using psutil.

    Gathers per-core CPU usage, frequencies, temperatures, and system
    load averages. Handles gracefully the case where certain metrics
    may not be available on all platforms.

    Class Attributes:
        name: Collector identifier
        default_interval: Default collection interval in seconds
        timeout: Maximum time allowed for collection
    """

    name: str = "cpu"
    default_interval: float = 1.0
    timeout: float = 5.0

    def __init__(self) -> None:
        """Initialize the CPU collector."""
        super().__init__()
        self._temp_sensor_name: str | None = None

    def _get_cpu_temps(self) -> dict[int, float]:
        """Get CPU core temperatures if available.

        Returns:
            Dictionary mapping core index to temperature in Celsius.
            Empty dict if temperatures are unavailable.
        """
        temps: dict[int, float] = {}

        try:
            # Use cached check for sensors availability
            if not _has_temperature_sensors():
                return temps

            sensor_data = psutil.sensors_temperatures()
            if not sensor_data:
                return temps

            # If we already found the sensor name, use it directly
            if self._temp_sensor_name and self._temp_sensor_name in sensor_data:
                for idx, temp in enumerate(sensor_data[self._temp_sensor_name]):
                    temps[idx] = temp.current
                return temps

            # Try to find CPU temperature sensors
            # Different systems use different sensor names
            sensor_names = ["coretemp", "cpu_thermal", "k10temp", "zenpower", "cpu"]

            for sensor_name in sensor_names:
                if sensor_name in sensor_data:
                    self._temp_sensor_name = sensor_name
                    for idx, temp in enumerate(sensor_data[sensor_name]):
                        temps[idx] = temp.current
                    break

            # Fallback: use first available sensor with "cpu" in name
            if not temps:
                for name, readings in sensor_data.items():
                    if "cpu" in name.lower():
                        self._temp_sensor_name = name
                        for idx, temp in enumerate(readings):
                            temps[idx] = temp.current
                        break

        except Exception:
            # Temperature reading failed, return empty dict
            pass

        return temps

    async def collect(self) -> CPUData:
        """Collect current CPU metrics.

        Returns:
            CPUData with per-core usage, frequencies, temperatures,
            and system load averages.
        """
        # Get per-core CPU usage percentages
        # Note: First call may return 0.0 if no previous measurement exists
        cpu_percents = psutil.cpu_percent(percpu=True)

        # Get per-core frequencies if available
        cpu_freqs: list[float | None] = []
        try:
            freq_info = psutil.cpu_freq(percpu=True)
            if freq_info:
                cpu_freqs = [f.current if f else None for f in freq_info]
            else:
                # Some systems return None for percpu=True, try without
                freq_single = psutil.cpu_freq(percpu=False)
                if freq_single:
                    # Apply same frequency to all cores
                    cpu_freqs = [freq_single.current] * len(cpu_percents)
                else:
                    cpu_freqs = [None] * len(cpu_percents)
        except Exception:
            cpu_freqs = [None] * len(cpu_percents)

        # Get temperatures if available
        temps = self._get_cpu_temps()

        # Build per-core data
        cores: list[CPUCore] = []
        for idx, usage in enumerate(cpu_percents):
            freq = cpu_freqs[idx] if idx < len(cpu_freqs) else None
            temp = temps.get(idx)

            cores.append(
                CPUCore(
                    id=idx,
                    usage_percent=usage,
                    freq_mhz=freq,
                    temp_celsius=temp,
                )
            )

        # Get load averages
        load_avg = psutil.getloadavg()

        return CPUData(
            source=self.name,
            cores=cores,
            load_avg_1min=load_avg[0],
            load_avg_5min=load_avg[1],
            load_avg_15min=load_avg[2],
        )

    def get_schema(self) -> type[CPUData]:
        """Return the Pydantic model class for this collector data.

        Returns:
            The CPUData class
        """
        return CPUData


class CPUPane(PanePlugin):
    """CPU monitoring pane plugin.

    Displays real-time CPU metrics including per-core usage, frequencies,
    temperatures, and system load averages.

    Class Attributes:
        name: Plugin identifier
        display_name: Human-readable name for UI
        version: Plugin version
        description: Brief description of functionality
        default_refresh_interval: Seconds between data collection
    """

    name: str = "cpu"
    display_name: str = "CPU Monitor"
    version: str = "0.1.0"
    description: str = "Real-time CPU usage, frequency, temperature, and load monitoring"
    default_refresh_interval: float = 1.0

    def __init__(self) -> None:
        """Initialize the CPU pane plugin."""
        super().__init__()
        self._collector: CPUCollector | None = None
        self._cached_widget = None  # Cache widget to preserve sparkline history

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration
        """
        super().initialize(config)
        self._collector = CPUCollector()
        if config:
            self._collector.initialize(config)
        else:
            self._collector.initialize()

    def shutdown(self) -> None:
        """Clean up plugin resources."""
        if self._collector:
            self._collector.shutdown()
            self._collector = None
        self._cached_widget = None
        super().shutdown()

    async def collect_data(self) -> CPUData:
        """Collect current CPU data.

        Returns:
            CPUData with current CPU metrics

        Raises:
            RuntimeError: If collector is not initialized
        """
        if self._collector is None:
            # Initialize collector if not already done
            self._collector = CPUCollector()
            self._collector.initialize()

        return await self._collector.collect()

    def render_tui(self, data: MetricData) -> Widget:
        """Render collected data as a Textual widget.

        Caches the widget instance to preserve sparkline history across refreshes.

        Args:
            data: The CPUData from the most recent collection

        Returns:
            A Textual Widget to display in the pane
        """
        # Import here to avoid circular imports and allow running without textual
        from textual.widgets import Label

        from uptop.tui.panes.cpu_widget import CPUWidget

        if not isinstance(data, CPUData):
            return Label("Invalid CPU data")

        # Reuse cached widget to preserve sparkline history
        if self._cached_widget is None:
            self._cached_widget = CPUWidget()

        self._cached_widget.update_data(data)
        return self._cached_widget

    def get_schema(self) -> type[CPUData]:
        """Return the Pydantic model class for this pane data.

        Returns:
            The CPUData class
        """
        return CPUData

    def get_ai_help_docs(self) -> str:
        """Return markdown documentation for --ai-help output.

        Returns:
            Markdown-formatted string describing the plugin
        """
        return """## CPU Monitor

The CPU Monitor pane displays real-time CPU metrics:

### Metrics Collected
- **Per-Core Usage**: CPU utilization percentage for each core (0-100%)
- **CPU Frequency**: Current clock speed in MHz (when available)
- **Temperature**: Core temperature in Celsius (when sensors are available)
- **Load Averages**: System load over 1, 5, and 15 minutes

### Configuration Options
- `interval`: Collection interval in seconds (default: 1.0)

### Metric Types
- **Gauges**: usage_percent, freq_mhz, temp_celsius, load_avg_*

### Notes
- CPU temperature sensors may not be available on all systems (especially macOS)
- First collection may show 0% usage as it requires a baseline measurement
- Load averages represent the number of processes in a runnable state
"""
