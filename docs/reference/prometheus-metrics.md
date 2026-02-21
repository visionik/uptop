# Prometheus Metrics

uptop can output system metrics in [Prometheus exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/) for integration with Prometheus, Grafana, and other monitoring stacks.

## Usage

```bash
# Single snapshot
uptop --prometheus --once

# Continuous output
uptop --prometheus --stream --interval 15
```

### Textfile Collector Integration

Write metrics to a file for Prometheus `node_exporter` textfile collector:

```bash
uptop --prometheus --once > /var/lib/node_exporter/textfile/uptop.prom
```

## Metrics Reference

### CPU

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `uptop_cpu_usage_percent` | gauge | `core` | CPU usage percentage per core |
| `uptop_cpu_freq_mhz` | gauge | `core` | CPU frequency in MHz per core |

### Memory

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `uptop_memory_bytes` | gauge | `type` | Memory in bytes (`total`, `used`, `free`, `available`, `cached`) |

### Network

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `uptop_network_bytes_total` | counter | `interface`, `direction` | Total bytes (`sent`/`recv`) per interface |

### Disk

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `uptop_disk_usage_bytes` | gauge | `mountpoint`, `type` | Disk usage in bytes (`total`, `used`, `free`) per mount |
| `uptop_disk_io_bytes_total` | counter | `disk`, `direction` | Total I/O bytes (`read`/`write`) per disk |

### Processes

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `uptop_process_count` | gauge | `state` | Number of processes by state |

## Metric Types

uptop uses the `MetricType` system to annotate fields as counters or gauges, ensuring correct `# TYPE` comments in Prometheus output:

- **counter**: Monotonically increasing values (e.g., `bytes_total`). Use `rate()` or `increase()` in PromQL.
- **gauge**: Values that can go up and down (e.g., `usage_percent`, `temperature`). Use `avg()`, `min()`, `max()` in PromQL.

## Custom Plugin Metrics

Plugin authors can use `gauge_field()` and `counter_field()` helpers from `uptop.models.base` to annotate their data models. The Prometheus formatter will automatically generate correct TYPE annotations:

```python
from uptop.models.base import MetricData, gauge_field, counter_field

class MyData(MetricData):
    current_value: float = gauge_field("Current measurement")
    total_events: int = counter_field("Total event count", ge=0)
```
