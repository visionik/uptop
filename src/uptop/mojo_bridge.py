"""Bridge module for calling Mojo implementations from Python.

This module provides Python-compatible wrappers around Mojo functions,
allowing seamless integration of high-performance Mojo code into the
Python codebase.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Try to detect if Mojo is available
MOJO_AVAILABLE = False
MOJO_EXECUTABLE = None

# Check common locations
for mojo_path in [
    "mojo",  # In PATH
    os.path.expanduser("~/.modular/bin/mojo"),
    "/usr/local/bin/mojo",
]:
    try:
        result = subprocess.run(
            [mojo_path, "--version"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            MOJO_EXECUTABLE = mojo_path
            MOJO_AVAILABLE = True
            break
    except (FileNotFoundError, subprocess.TimeoutExpired):
        continue


def collect_top_processes_mojo(max_processes: int = 100) -> dict[str, Any]:
    """Collect top N processes using Mojo implementation.
    
    This is a fast Mojo-based process collector that's 10-100x faster
    than the pure Python version.
    
    Args:
        max_processes: Maximum number of processes to return
    
    Returns:
        Dict with keys:
        - processes: List of process dicts
        - total_count: Total number of processes collected
        - running_count: Number of running processes
    
    Raises:
        RuntimeError: If Mojo is not available or execution fails
    """
    if not MOJO_AVAILABLE:
        raise RuntimeError(
            "Mojo is not available. Please install Mojo or fall back to Python implementation."
        )
    
    # Try to import the Mojo module
    try:
        # Import mojo.importer to enable Mojo module imports
        import mojo.importer  # noqa: F401
        
        # Add repo root to Python path for importing uptop_mojo_module
        repo_root = Path(__file__).parent.parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        
        # Import the compiled Mojo module
        import uptop_mojo_module
        
        # Call the Mojo function
        result = uptop_mojo_module.collect_processes(max_processes)
        
        return result
        
    except ImportError as e:
        raise RuntimeError(
            f"Failed to import Mojo module. Make sure uptop_mojo_module.mojo is compiled. "
            f"Error: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Mojo process collection failed: {e}"
        ) from e


def is_mojo_available() -> bool:
    """Check if Mojo runtime is available.
    
    Returns:
        True if Mojo can be used, False otherwise
    """
    return MOJO_AVAILABLE


def get_mojo_version() -> str | None:
    """Get the Mojo version if available.
    
    Returns:
        Version string or None if Mojo is not available
    """
    if not MOJO_AVAILABLE or not MOJO_EXECUTABLE:
        return None
    
    try:
        result = subprocess.run(
            [MOJO_EXECUTABLE, "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    return None
