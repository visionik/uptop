#!/usr/bin/env python3
"""Profile uptop to find performance bottlenecks.

Usage:
    python profile-uptop.py [options]

Options:
    --json      Profile JSON output mode
    --tui       Profile TUI mode (runs for 5 seconds)
    --sort KEY  Sort by: cumtime, tottime, calls (default: cumtime)
    --top N     Show top N functions (default: 50)
"""

import cProfile
import pstats
import sys
import time
from io import StringIO


def profile_json_mode():
    """Profile a single JSON output."""
    from uptop.cli_runner import run_cli_mode
    from uptop.config import load_config
    
    config = load_config()
    run_cli_mode(
        format_name="json",
        pane_names=None,
        once=True,
        stream=False,
        config=config,
    )


def profile_tui_mode():
    """Profile TUI mode for 5 seconds."""
    import threading
    from uptop.tui import run_app
    from uptop.config import load_config
    
    config = load_config()
    
    # Run TUI in a thread and stop after 5 seconds
    def run_tui():
        try:
            run_app(config, debug_mode=True)
        except KeyboardInterrupt:
            pass
    
    thread = threading.Thread(target=run_tui, daemon=True)
    thread.start()
    time.sleep(5)
    # Send interrupt to stop
    import os
    import signal
    os.kill(os.getpid(), signal.SIGINT)
    thread.join(timeout=2)


def main():
    """Main profiling entry point."""
    sort_key = "cumtime"
    top_n = 50
    mode = "json"
    
    # Parse simple args
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--tui":
            mode = "tui"
        elif arg == "--json":
            mode = "json"
        elif arg == "--sort" and i + 1 < len(sys.argv) - 1:
            sort_key = sys.argv[i + 2]
        elif arg == "--top" and i + 1 < len(sys.argv) - 1:
            top_n = int(sys.argv[i + 2])
    
    print(f"Profiling uptop in {mode} mode...")
    print(f"Sort by: {sort_key}, showing top {top_n} functions")
    print("-" * 80)
    
    # Profile the selected mode
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        if mode == "tui":
            profile_tui_mode()
        else:
            profile_json_mode()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        profiler.disable()
    
    # Print stats
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats(sort_key)
    stats.print_stats(top_n)
    
    print(stream.getvalue())
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    stats.print_stats(10)
    
    # Save to file
    output_file = f"profile-{mode}-{int(time.time())}.prof"
    stats.dump_stats(output_file)
    print(f"\nProfile saved to: {output_file}")
    print(f"View with: python -m pstats {output_file}")


if __name__ == "__main__":
    main()
