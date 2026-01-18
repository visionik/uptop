"""uptop - Mojo entry point that bridges to Python implementation.

This provides a Mojo entry point that:
1. Uses fast Mojo metrics collection (metrics.mojo)
2. Bridges to Python for CLI/TUI functionality
3. Demonstrates hybrid Mojo/Python architecture
"""

from python import Python
from sys import argv
from metrics import collect_cpu_metrics, collect_memory_metrics


fn print_usage():
    """Print usage information."""
    print("uptop - Universal Performance & Telemetry Output")
    print()
    print("Usage:")
    print("  uptop [options]")
    print()
    print("Options:")
    print("  --mojo-metrics    Show metrics using native Mojo (demo)")
    print("  --python          Run full Python version (default)")
    print("  --help, -h        Show this help")
    print()
    print("Examples:")
    print("  uptop --mojo-metrics    # Fast Mojo metrics collection")
    print("  uptop --python          # Full Python TUI/CLI")


fn run_mojo_metrics() raises:
    """Run the simple Mojo metrics demo."""
    print("=== uptop (Mojo mode) ===")
    print()
    
    var cpu = collect_cpu_metrics()
    print("CPU:")
    print("  Cores:", cpu.core_count)
    print("  Usage:", cpu.total_usage, "%")
    print("  Load (1m/5m/15m):", cpu.load_avg_1min, "/", cpu.load_avg_5min, "/", cpu.load_avg_15min)
    print()
    
    var mem = collect_memory_metrics()
    print("Memory:")
    print("  Total:", mem.total_bytes // (1024 * 1024 * 1024), "GB")
    print("  Used:", mem.used_bytes // (1024 * 1024 * 1024), "GB")
    print("  Available:", mem.available_bytes // (1024 * 1024 * 1024), "GB")
    print("  Usage:", mem.percent, "%")
    print()
    print("Swap:")
    print("  Total:", mem.swap_total // (1024 * 1024 * 1024), "GB")
    print("  Used:", mem.swap_used // (1024 * 1024 * 1024), "GB")
    print("  Usage:", mem.swap_percent, "%")


fn run_python_version(pass_args: Bool = True) raises:
    """Run the full Python version with all features."""
    # Add src directory to Python path
    Python.add_to_path("src")
    
    # Import sys to manipulate argv if needed
    var sys = Python.import_module("sys")
    
    # Filter out --python and --mojo-metrics flags when passing to Python
    if pass_args:
        var args = argv()
        var filtered_args = Python.list()
        
        # Skip first arg (program name) and filter out Mojo-specific flags
        for i in range(1, len(args)):
            var arg = args[i]
            if arg != "--python" and arg != "--mojo-metrics":
                filtered_args.append(arg)
        
        # Replace sys.argv with filtered args
        var new_argv = Python.list()
        new_argv.append("uptop")  # Program name
        for item in filtered_args:
            new_argv.append(item)
        sys.argv = new_argv
    
    # Import the Python uptop module
    var uptop_main = Python.import_module("uptop.__main__")
    
    # Call the Python main function
    var exit_code = uptop_main.main()
    
    # Exit with the same code
    if exit_code.__int__() != 0:
        # Note: Mojo doesn't have sys.exit, so we raise
        raise Error("Python uptop exited with code: " + String(exit_code.__int__()))


fn main() raises:
    """Main entry point."""
    # Get command line arguments
    var args = argv()
    
    # Parse simple flags
    var show_help = False
    var use_mojo = False
    var use_python = False
    
    # Simple argument parsing
    for i in range(len(args)):
        var arg = args[i]
        if arg == "--help" or arg == "-h":
            show_help = True
        elif arg == "--mojo-metrics":
            use_mojo = True
        elif arg == "--python":
            use_python = True
    
    # Handle help
    if show_help:
        print_usage()
        return
    
    # Run the appropriate mode
    if use_mojo:
        run_mojo_metrics()
    elif use_python or len(args) > 1:
        # If any other args, pass through to Python
        run_python_version()
    else:
        # Default: run Python version for full functionality
        print("Note: Running Python version (use --mojo-metrics for Mojo demo)")
        print()
        run_python_version()
