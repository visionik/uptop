"""Mojo implementation of performance-critical metrics collection.

This module ports the CPU and memory collectors from Python to Mojo
for improved performance. It still uses psutil via Python interop for
actual data collection, but provides a native Mojo interface.
"""

from python import Python


struct CPUMetrics:
    """CPU metrics collected from the system."""
    var core_count: Int
    var total_usage: Float64
    var load_avg_1min: Float64
    var load_avg_5min: Float64
    var load_avg_15min: Float64
    
    fn __init__(
        out self,
        core_count: Int,
        total_usage: Float64,
        load_avg_1min: Float64,
        load_avg_5min: Float64,
        load_avg_15min: Float64
    ):
        self.core_count = core_count
        self.total_usage = total_usage
        self.load_avg_1min = load_avg_1min
        self.load_avg_5min = load_avg_5min
        self.load_avg_15min = load_avg_15min


struct MemoryMetrics:
    """Memory metrics collected from the system."""
    var total_bytes: Int
    var used_bytes: Int
    var available_bytes: Int
    var percent: Float64
    var swap_total: Int
    var swap_used: Int
    var swap_percent: Float64
    
    fn __init__(
        out self,
        total_bytes: Int,
        used_bytes: Int,
        available_bytes: Int,
        percent: Float64,
        swap_total: Int,
        swap_used: Int,
        swap_percent: Float64
    ):
        self.total_bytes = total_bytes
        self.used_bytes = used_bytes
        self.available_bytes = available_bytes
        self.percent = percent
        self.swap_total = swap_total
        self.swap_used = swap_used
        self.swap_percent = swap_percent


fn collect_cpu_metrics() raises -> CPUMetrics:
    """Collect CPU metrics using psutil via Python interop.
    
    Returns:
        CPUMetrics struct with current CPU statistics.
    
    Raises:
        If psutil import or data collection fails.
    """
    var psutil = Python.import_module("psutil")
    
    # Get CPU count
    var cpu_count_obj = psutil.cpu_count(logical=True)
    var core_count = Int(cpu_count_obj)
    
    # Get overall CPU usage (blocking call, interval=1 for accuracy)
    var cpu_percent_obj = psutil.cpu_percent(interval=0.1)
    var total_usage = Float64(cpu_percent_obj)
    
    # Get load averages
    var load_avg = psutil.getloadavg()
    var load_1 = Float64(load_avg[0])
    var load_5 = Float64(load_avg[1])
    var load_15 = Float64(load_avg[2])
    
    return CPUMetrics(
        core_count,
        total_usage,
        load_1,
        load_5,
        load_15
    )


fn collect_memory_metrics() raises -> MemoryMetrics:
    """Collect memory metrics using psutil via Python interop.
    
    Returns:
        MemoryMetrics struct with current memory statistics.
    
    Raises:
        If psutil import or data collection fails.
    """
    var psutil = Python.import_module("psutil")
    
    # Virtual memory
    var vm = psutil.virtual_memory()
    var total = Int(vm.total)
    var used = Int(vm.used)
    var available = Int(vm.available)
    var percent = Float64(vm.percent)
    
    # Swap memory
    var sm = psutil.swap_memory()
    var swap_total = Int(sm.total)
    var swap_used = Int(sm.used)
    var swap_percent = Float64(sm.percent)
    
    return MemoryMetrics(
        total,
        used,
        available,
        percent,
        swap_total,
        swap_used,
        swap_percent
    )


fn format_bytes(bytes: Int) -> String:
    """Format bytes as human-readable string (KB, MB, GB, etc).
    
    Args:
        bytes: Number of bytes to format.
    
    Returns:
        Formatted string like "4.2 GB".
    """
    var units = ["B", "KB", "MB", "GB", "TB"]
    var value = Float64(bytes)
    var unit_idx = 0
    
    while value >= 1024.0 and unit_idx < 4:
        value = value / 1024.0
        unit_idx += 1
    
    # Simple formatting without printf-style
    return String(value) + " " + units[unit_idx]
