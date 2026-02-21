# CLI Mode

CLI mode outputs system metrics in structured formats suitable for scripting, piping, and integration with monitoring systems.

## Entering CLI Mode

CLI mode activates automatically when:

- A format flag is passed (`--json`, `--markdown`, `--prometheus`)
- A stream flag is passed (`--stream`, `--continuous`)
- stdout is not a TTY (e.g., piped to another command)

Or explicitly:

```bash
uptop cli --json
```

## Output Formats

### JSON

```bash
# Single snapshot, pretty-printed
uptop --json --once

# Compact JSON
uptop --json --once --no-pretty

# Stream as NDJSON (newline-delimited)
uptop --json --stream --interval 5
```

Example output:

```json
{
  "timestamp": "2026-02-20T10:30:00Z",
  "panes": {
    "cpu": {
      "cores": [
        {"id": 0, "usage_percent": 45.2, "frequency_mhz": 2800}
      ],
      "load_avg": {"1min": 1.2, "5min": 1.5, "15min": 1.8}
    },
    "memory": {
      "total_bytes": 17179869184,
      "used_bytes": 8589934592,
      "percent": 50.0
    }
  }
}
```

### Prometheus

```bash
uptop --prometheus --once
```

Outputs metrics in Prometheus exposition format with proper TYPE annotations:

```
# TYPE uptop_cpu_usage_percent gauge
uptop_cpu_usage_percent{core="0"} 45.2
uptop_cpu_usage_percent{core="1"} 32.1
# TYPE uptop_memory_bytes gauge
uptop_memory_bytes{type="total"} 17179869184
uptop_memory_bytes{type="used"} 8589934592
# TYPE uptop_network_bytes_total counter
uptop_network_bytes_total{interface="eth0",direction="sent"} 1234567890
```

### Markdown

```bash
uptop --markdown --once
```

Outputs tables suitable for reports or documentation.

## Output Modes

| Mode | Flag | Behavior |
|------|------|----------|
| **Once** | `--once` | Collect a single snapshot and exit |
| **Stream** | `--stream` | Continuous NDJSON output at each interval |
| **Continuous** | `--continuous` | ANSI in-place redraw (like `watch`) |

`--once` is the default when stdout is not a TTY.

## Filtering

### Select Specific Panes

```bash
# Only CPU and memory data
uptop --json --once --panes cpu,memory

# Only processes
uptop --json --once --panes processes
```

### JMESPath Queries

Filter JSON output with JMESPath expressions (requires the `query` extra):

```bash
pip install uptop[query]
uptop --json --once --query "panes.cpu.cores[0].usage_percent"
```

## Common Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | `-j` | JSON output format |
| `--markdown` | `-m` | Markdown output format |
| `--prometheus` | | Prometheus output format |
| `--once` | `-o` | Single snapshot, then exit |
| `--stream` | `-s` | Continuous streaming output |
| `--continuous` | | ANSI in-place redraw |
| `--interval N` | `-i N` | Refresh interval in seconds |
| `--panes LIST` | `-p LIST` | Comma-separated pane names |
| `--pretty/--no-pretty` | | Pretty-print output |
| `--query EXPR` | `-q EXPR` | JMESPath filter expression |
| `--config PATH` | `-c PATH` | Custom config file path |

## Scripting Examples

### Pipe to jq

```bash
uptop --json --once | jq '.panes.cpu.load_avg'
```

### Monitor CPU in a Loop

```bash
uptop --json --stream --panes cpu --interval 2 | while read -r line; do
  echo "$line" | jq -r '.panes.cpu.cores[0].usage_percent'
done
```

### Feed Prometheus

Point your Prometheus scraper at a simple HTTP wrapper, or write the output to a file for node_exporter's textfile collector:

```bash
uptop --prometheus --once > /var/lib/node_exporter/textfile/uptop.prom
```

### Markdown Report to File

```bash
uptop --markdown --once > system-report.md
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration or runtime error |
| 130 | Interrupted by SIGINT (Ctrl+C) |
