# Installation

## Requirements

- **Python** 3.11 or higher
- **Operating System**: Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+) or macOS 12+
- Windows is not supported

## Install from PyPI

```bash
pip install uptop
```

### Optional Extras

```bash
# GPU monitoring (NVIDIA/AMD)
pip install uptop[gpu]

# JMESPath query support for CLI output filtering
pip install uptop[query]

# All optional dependencies
pip install uptop[all]
```

## Install from Source

```bash
git clone https://github.com/yourusername/uptop.git
cd uptop
pip install -e .
```

## Development Installation

For contributing or developing plugins, install with development dependencies:

### Prerequisites

- Python 3.11+
- [Task](https://taskfile.dev/) (task runner)
- Git

### Steps

```bash
git clone https://github.com/yourusername/uptop.git
cd uptop

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
task install
# Or directly: pip install -e ".[dev]"

# Verify everything works
task check
```

The `task check` command runs the full quality pipeline: formatting, linting, type checking, tests, and coverage verification.

## Verify Installation

```bash
uptop --version
```

## Platform Notes

### Linux

uptop reads from `/proc` for richer process and network information. Some features may require elevated permissions:

- Temperature sensors: accessible without root on most systems
- Process kill: requires appropriate permissions for the target process

### macOS

uptop uses `psutil` which wraps system calls on macOS. Some differences:

- Memory breakdown shows wired/active/inactive when available
- GPU monitoring is limited on Apple Silicon (best-effort via `system_profiler`)
- Temperature monitoring may require `sudo` for some sensors via `powermetrics`
