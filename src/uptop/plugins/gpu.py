"""GPU pane plugin for uptop.

This module provides the GPU monitoring pane that displays GPU usage and info.
It includes:
- GPUInfo model for static GPU information
- GPUMetrics model for dynamic GPU metrics
- GPUData aggregated model
- GPUCollector for gathering metrics via system tools
- GPUPane plugin for TUI display

Supports:
- Apple Silicon (M1/M2/M3/M4): via system_profiler and powermetrics
- Future: NVIDIA (pynvml), AMD (pyamdgpuinfo), Intel
"""

from __future__ import annotations

import asyncio
import contextlib
from functools import lru_cache
import json
import os
import platform
import subprocess
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from uptop.collectors.base import DataCollector
from uptop.models.base import DisplayMode, MetricData, gauge_field
from uptop.plugin_api.base import PanePlugin

if TYPE_CHECKING:
    from textual.widget import Widget


# Cache GPU detection - doesn't change during runtime
@lru_cache(maxsize=1)
def _detect_gpu_platform() -> str:
    """Detect the GPU platform.

    Returns:
        Platform string: 'apple_silicon', 'nvidia', 'amd', 'intel', or 'unknown'
    """
    system = platform.system()

    if system == "Darwin":
        # Check if Apple Silicon
        machine = platform.machine()
        if machine == "arm64":
            return "apple_silicon"
        # Intel Mac - could have discrete GPU
        return "intel"

    if system == "Linux":
        # Try to detect NVIDIA
        try:
            import pynvml  # noqa: F401

            return "nvidia"
        except ImportError:
            pass

        # Try to detect AMD
        try:
            import pyamdgpuinfo  # noqa: F401

            return "amd"
        except ImportError:
            pass

    return "unknown"


@lru_cache(maxsize=1)
def _get_apple_gpu_info() -> dict | None:
    """Get Apple GPU info via system_profiler (cached).

    Returns:
        Dictionary with GPU info or None if unavailable
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            displays = data.get("SPDisplaysDataType", [])
            if displays:
                return displays[0]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return None


# Track if powermetrics is available (requires sudo or root)
_powermetrics_available: bool | None = None


def _is_root() -> bool:
    """Check if running as root."""
    return os.geteuid() == 0


def _check_powermetrics_available() -> bool:
    """Check if powermetrics is available (has sudo access or running as root).

    Returns:
        True if powermetrics can be run, False otherwise
    """
    global _powermetrics_available
    if _powermetrics_available is not None:
        return _powermetrics_available

    try:
        # Build command - skip sudo if already root
        if _is_root():
            cmd = ["powermetrics", "-n", "1", "--samplers", "gpu_power"]
        else:
            cmd = ["sudo", "-n", "powermetrics", "-n", "1", "--samplers", "gpu_power"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
        )
        _powermetrics_available = result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        _powermetrics_available = False

    return _powermetrics_available


def _get_memory_pressure() -> float | None:
    """Get system memory pressure percentage.

    Returns:
        Memory pressure as percentage (0-100) or None if unavailable
    """
    try:
        result = subprocess.run(
            ["memory_pressure"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            # Parse "System-wide memory free percentage: XX%"
            for line in result.stdout.split("\n"):
                if "free percentage" in line.lower():
                    # Extract percentage
                    parts = line.split(":")
                    if len(parts) >= 2:
                        pct_str = parts[1].strip().rstrip("%")
                        free_pct = float(pct_str)
                        # Convert free to pressure (100 - free = pressure)
                        return 100.0 - free_pct
    except (subprocess.TimeoutExpired, ValueError, Exception):
        pass
    return None


def _get_powermetrics_gpu_usage() -> float | None:
    """Get GPU usage from powermetrics (requires sudo or root).

    Returns:
        GPU usage percentage (0-100) or None if unavailable
    """
    if not _check_powermetrics_available():
        return None

    try:
        # Build command - skip sudo if already root
        base_cmd = ["powermetrics", "-n", "1", "--samplers", "gpu_power", "-o", "plist"]
        cmd = base_cmd if _is_root() else ["sudo", "-n", *base_cmd]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            # Parse plist output for GPU usage
            # Look for gpu_busy or similar metrics
            import plistlib

            data = plistlib.loads(result.stdout.encode())

            # Try to find GPU usage in various possible locations
            if "gpu" in data:
                gpu_data = data["gpu"]
                if "gpu_busy" in gpu_data:
                    return float(gpu_data["gpu_busy"]) * 100.0

            # Alternative: look in processor data
            if "processor" in data:
                proc_data = data["processor"]
                if "gpu_busy" in proc_data:
                    return float(proc_data["gpu_busy"]) * 100.0

    except Exception:
        pass
    return None


class GPUInfo(BaseModel):
    """Model for static GPU information.

    Attributes:
        name: GPU model name (e.g., "Apple M4 Max")
        vendor: GPU vendor (e.g., "Apple", "NVIDIA", "AMD")
        cores: Number of GPU cores (if available)
        metal_version: Metal API version (Apple only)
        vram_mb: Dedicated VRAM in MB (None for unified memory)
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="GPU model name")
    vendor: str = Field(..., description="GPU vendor")
    cores: int | None = Field(None, description="Number of GPU cores", ge=0)
    metal_version: str | None = Field(None, description="Metal API version")
    vram_mb: int | None = Field(None, description="Dedicated VRAM in MB", ge=0)


class GPUMetrics(BaseModel):
    """Model for dynamic GPU metrics.

    Attributes:
        utilization_percent: GPU utilization (0-100), None if unavailable
        memory_used_mb: GPU memory used in MB
        memory_total_mb: Total GPU memory in MB
        temperature_celsius: GPU temperature in Celsius
    """

    model_config = ConfigDict(frozen=True)

    utilization_percent: float | None = gauge_field(
        "GPU utilization percentage", default=None, ge=0.0, le=100.0
    )
    memory_used_mb: float | None = gauge_field("GPU memory used in MB", default=None, ge=0.0)
    memory_total_mb: float | None = gauge_field("Total GPU memory in MB", default=None, ge=0.0)
    temperature_celsius: float | None = gauge_field("GPU temperature in Celsius", default=None)


class GPUData(MetricData):
    """Aggregated GPU data model.

    Contains GPU information and metrics.

    Attributes:
        gpus: List of GPU information
        metrics: Current GPU metrics (if available)
        memory_pressure_percent: System memory pressure (Apple Silicon)
        platform: Detected GPU platform
        powermetrics_available: Whether powermetrics is accessible
    """

    gpus: list[GPUInfo] = Field(default_factory=list, description="GPU information")
    metrics: GPUMetrics | None = Field(None, description="GPU metrics")
    memory_pressure_percent: float | None = gauge_field(
        "System memory pressure percentage", default=None, ge=0.0, le=100.0
    )
    platform: str = Field("unknown", description="GPU platform")
    powermetrics_available: bool = Field(False, description="Whether powermetrics is accessible")

    @property
    def primary_gpu(self) -> GPUInfo | None:
        """Get the primary GPU (first in list)."""
        return self.gpus[0] if self.gpus else None

    @property
    def gpu_usage_percent(self) -> float | None:
        """Get GPU usage percentage if available."""
        if self.metrics:
            return self.metrics.utilization_percent
        return None


class GPUCollector(DataCollector[GPUData]):
    """Collector for GPU metrics.

    Gathers GPU information and metrics based on the detected platform.
    Handles platform differences gracefully.
    """

    name: str = "gpu"
    default_interval: float = 2.0
    timeout: float = 5.0

    async def collect(self) -> GPUData:
        """Collect current GPU statistics.

        Returns:
            GPUData containing GPU info and metrics

        Raises:
            Exception: If GPU info cannot be retrieved
        """
        gpu_platform = _detect_gpu_platform()

        if gpu_platform == "apple_silicon":
            return await self._collect_apple_silicon()

        # Fallback for unknown platforms
        return GPUData(
            gpus=[],
            metrics=None,
            memory_pressure_percent=None,
            platform=gpu_platform,
            powermetrics_available=False,
            source="gpu",
        )

    async def _collect_apple_silicon(self) -> GPUData:
        """Collect GPU data for Apple Silicon Macs."""
        gpus: list[GPUInfo] = []

        # Get static GPU info (cached)
        gpu_info = _get_apple_gpu_info()
        if gpu_info:
            name = gpu_info.get("sppci_model", gpu_info.get("_name", "Unknown GPU"))
            vendor = "Apple"

            # Parse core count
            cores = None
            cores_str = gpu_info.get("sppci_cores")
            if cores_str:
                with contextlib.suppress(ValueError):
                    cores = int(cores_str)

            # Parse Metal version
            metal_version = None
            metal_str = gpu_info.get("spdisplays_mtlgpufamilysupport", "")
            if metal_str:
                # Convert "spdisplays_metal4" to "Metal 4"
                metal_version = metal_str.replace("spdisplays_", "").replace("metal", "Metal ")

            gpus.append(
                GPUInfo(
                    name=name,
                    vendor=vendor,
                    cores=cores,
                    metal_version=metal_version,
                    vram_mb=None,  # Unified memory
                )
            )

        # Get dynamic metrics
        # Run these in parallel
        loop = asyncio.get_event_loop()

        memory_pressure = await loop.run_in_executor(None, _get_memory_pressure)
        gpu_usage = await loop.run_in_executor(None, _get_powermetrics_gpu_usage)

        metrics = None
        if gpu_usage is not None:
            metrics = GPUMetrics(
                utilization_percent=gpu_usage,
                memory_used_mb=None,
                memory_total_mb=None,
                temperature_celsius=None,
            )

        return GPUData(
            gpus=gpus,
            metrics=metrics,
            memory_pressure_percent=memory_pressure,
            platform="apple_silicon",
            powermetrics_available=_check_powermetrics_available(),
            source="gpu",
        )

    def get_schema(self) -> type[GPUData]:
        """Return the GPUData model class.

        Returns:
            The GPUData Pydantic model class
        """
        return GPUData


class GPUPane(PanePlugin):
    """GPU monitoring pane plugin.

    Displays GPU information and usage in the TUI. Shows:
    - GPU model, cores, Metal version (Apple Silicon)
    - GPU utilization (if powermetrics available)
    - Memory pressure (Apple Silicon unified memory)
    """

    name: str = "gpu"
    display_name: str = "GPU"
    version: str = "0.1.0"
    description: str = "Monitor GPU usage and information"
    author: str = "uptop"
    default_refresh_interval: float = 2.0

    def __init__(self) -> None:
        """Initialize the GPU pane."""
        super().__init__()
        self._collector = GPUCollector()
        self._cached_widget = None  # Cache widget to preserve sparkline history

    async def collect_data(self) -> GPUData:
        """Collect current GPU metrics.

        Returns:
            GPUData with current GPU information and metrics
        """
        return await self._collector.collect()

    def render_tui(
        self,
        data: MetricData,
        size: tuple[int, int] | None = None,
        mode: DisplayMode | None = None,
    ) -> Widget:
        """Render GPU data as a Textual widget.

        Caches the widget instance to preserve sparkline history across refreshes.

        Args:
            data: The GPUData from collect_data()
            size: Optional (width, height) in cells (currently unused)
            mode: Optional DisplayMode (currently unused, always full display)

        Returns:
            A Textual widget displaying GPU information
        """
        from textual.widgets import Label

        from uptop.tui.panes.gpu_widget import GPUWidget

        # Type check for mypy
        if not isinstance(data, GPUData):
            return Label("Invalid data type for GPUPane")

        # Reuse cached widget to preserve sparkline history
        if self._cached_widget is None:
            self._cached_widget = GPUWidget()

        self._cached_widget.update_data(data)
        return self._cached_widget

    def get_schema(self) -> type[GPUData]:
        """Return the GPUData model class.

        Returns:
            The GPUData Pydantic model class
        """
        return GPUData
