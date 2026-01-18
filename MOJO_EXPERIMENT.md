# Mojo Port Experiment

This branch (`experiment/mojo-port`) explores porting performance-critical parts of uptop from Python to Mojo.

## Overview

Mojo is a new programming language that combines Python's ease of use with C-level performance. It can:
- Run Python code natively (via embedded CPython)
- Provide 10-100x+ performance improvements for computational workloads
- Use static types and systems programming features (structs, memory ownership)

## What's Been Ported

### `metrics.mojo`
Contains Mojo implementations of:
- `CPUMetrics` struct - CPU metrics collection
- `MemoryMetrics` struct - Memory/swap metrics collection
- `collect_cpu_metrics()` - Fast CPU data gathering
- `collect_memory_metrics()` - Fast memory data gathering
- `format_bytes()` - Human-readable byte formatting

These still use `psutil` via Python interop but provide a native Mojo interface.

### `main.mojo`
Simple demo entry point that:
- Collects CPU metrics (cores, usage, load averages)
- Collects memory metrics (RAM, swap usage)
- Displays results in a readable format

## Running the Mojo Version

### Prerequisites
```bash
# Install mojo CLI via uv
uv tool install mojo --extra-index-url https://modular.gateway.scarf.sh/simple/

# Or install via pip
pip install mojo --extra-index-url https://modular.gateway.scarf.sh/simple/
```

### Run
```bash
# Point Mojo to the Python venv with psutil
MOJO_PYTHON=.venv/bin/python mojo main.mojo

# Or via uvx (doesn't require installing mojo globally)
MOJO_PYTHON=.venv/bin/python uvx --from mojo-compiler mojo main.mojo
```

## Architecture

```
┌─────────────────────────────────────┐
│         main.mojo (entry)           │
│   - Collect & display metrics       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      metrics.mojo (Mojo native)     │
│   - CPUMetrics struct               │
│   - MemoryMetrics struct            │
│   - Fast data collection            │
└──────────────┬──────────────────────┘
               │ Python interop
               ▼
┌─────────────────────────────────────┐
│       psutil (Python library)       │
│   - System metrics via OS APIs      │
└─────────────────────────────────────┘
```

## Performance Comparison

_TODO: Add benchmarks comparing Python vs Mojo versions_

Expected improvements:
- Data collection: 2-5x faster (less overhead)
- Data processing: 10-100x faster (when doing calculations on metrics)
- Memory usage: Lower (structs vs Python objects)

## Next Steps

Potential future work:
1. **Port more collectors**: Disk, network, process collectors
2. **Add native Mojo metrics processing**: Aggregation, filtering, transformations
3. **Create Mojo CLI**: Replace Typer with native argument parsing
4. **Benchmark suite**: Measure actual performance gains
5. **Hybrid architecture**: Keep TUI in Python (Textual), core in Mojo
6. **Zero-copy data transfer**: Optimize Python ↔ Mojo boundary

## Current Limitations

- Still depends on psutil (Python) for actual system calls
- No native TUI (still need Textual from Python)
- Cannot replace Python entry point yet (Typer/CLI still needed)
- Mojo is early stage - some features/stdlib incomplete

## Integration Strategy

### Gradual Migration Path

1. **Phase 1 (Current)**: Proof of concept with basic metrics
2. **Phase 2**: Port all collectors to Mojo
3. **Phase 3**: Create Python wrapper module that calls Mojo
4. **Phase 4**: Replace Python plugins with Mojo equivalents
5. **Phase 5**: Keep Python for TUI, Mojo for everything else

### Mixed Python/Mojo Project Structure

```
uptop/
├── mojo/                  # Mojo implementation
│   ├── metrics.mojo      # Core metrics (Mojo)
│   ├── collectors.mojo   # Data collectors (Mojo)
│   └── lib.mojo          # Utilities (Mojo)
├── src/uptop/            # Python implementation
│   ├── cli.py           # CLI (Python + Typer)
│   ├── tui/             # TUI (Python + Textual)
│   └── plugins/         # Plugins (Python, call Mojo)
└── pyproject.toml        # Project config
```

## Building for Distribution

```bash
# Compile Mojo to binary
mojo build main.mojo -o uptop-mojo

# Run compiled binary
MOJO_PYTHON=.venv/bin/python ./uptop-mojo
```

## Resources

- [Mojo Manual](https://docs.modular.com/mojo/manual/)
- [Mojo Python Interop](https://docs.modular.com/mojo/manual/python/)
- [Mojo vs Python Performance](https://www.modular.com/blog/mojo-vs-python-whats-the-difference)

## Contributing

This is an experimental branch. Feedback and contributions welcome!

See [CONTRIBUTING.md](./CONTRIBUTING.md) for general guidelines.
