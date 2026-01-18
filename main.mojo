"""Main entry point for uptop Mojo experiment.

This demonstrates using Mojo for performance-critical metrics collection
while delegating UI and other components to Python via interop.
"""

from metrics import collect_cpu_metrics, collect_memory_metrics, format_bytes


fn main() raises:
    """Main function - collect and display system metrics."""
    print("=== uptop Mojo Experiment ===\n")
    
    # Collect CPU metrics
    print("Collecting CPU metrics...")
    var cpu = collect_cpu_metrics()
    print("CPU Cores:", cpu.core_count)
    print("CPU Usage:", cpu.total_usage, "%")
    print("Load Average (1min):", cpu.load_avg_1min)
    print("Load Average (5min):", cpu.load_avg_5min)
    print("Load Average (15min):", cpu.load_avg_15min)
    print()
    
    # Collect memory metrics
    print("Collecting memory metrics...")
    var mem = collect_memory_metrics()
    print("Memory Total:", format_bytes(mem.total_bytes))
    print("Memory Used:", format_bytes(mem.used_bytes))
    print("Memory Available:", format_bytes(mem.available_bytes))
    print("Memory Usage:", mem.percent, "%")
    print()
    print("Swap Total:", format_bytes(mem.swap_total))
    print("Swap Used:", format_bytes(mem.swap_used))
    print("Swap Usage:", mem.swap_percent, "%")
    print()
    
    print("✓ Mojo metrics collection successful!")
