# Ping Monitoring Plugin - Quick Reference

## Overview
Network latency and availability monitoring plugin for uptop. Monitors configured hosts via ICMP ping with threshold-based alerting.

## Files

### Core Implementation
- **Models**: `src/uptop/plugins/ping_models.py`
  - `PingMetrics` - Single ping measurement
  - `HostPingResult` - Per-host aggregated results
  - `PingData` - Complete data for all hosts

- **Config**: `src/uptop/plugins/ping_config.py`
  - `PingPluginConfig` - Top-level configuration
  - `PingHostConfig` - Per-host settings
  - `PingThresholds` - Alert thresholds
  - `RetryDNSConfig` - DNS retry policy
  - `AutoDisableConfig` - Auto-disable settings

- **Collector**: `src/uptop/collectors/ping_collector.py`
  - `PingCollector` - Main collector class
  - Handles DNS resolution, ping execution, parsing, alerting

### Tests
- `tests/test_ping_models.py` - Model tests (254 lines)
- `tests/test_ping_config.py` - Config tests (292 lines)  
- `tests/test_ping_collector.py` - Collector tests (491 lines)

## Configuration

### Minimal Config
```yaml
ping:
  hosts:
    - host: example.com
    - host: 192.168.1.1
```

### Full Config with Overrides
```yaml
ping:
  enabled: true
  default_interval: 1.0        # Ping every 1 second
  default_timeout: 2.0         # 2 second timeout
  concurrent_limit: 10         # Max 10 parallel pings
  pings_per_check: 3           # Send 3 pings per check
  history_size: 300            # Keep 300 historical results
  
  # Global thresholds
  default_thresholds:
    warning_latency_ms: 100.0
    critical_latency_ms: 500.0
    warning_packet_loss_percent: 5.0
    critical_packet_loss_percent: 20.0
  
  # DNS retry settings
  retry_dns:
    enabled: true
    max_attempts: 3
    backoff_seconds: [1.0, 2.0, 4.0]
  
  # Auto-disable failing hosts
  auto_disable:
    enabled: true
    consecutive_failures_threshold: 10
  
  # Hosts to monitor
  hosts:
    - host: example.com
      # Uses all defaults
    
    - host: 192.168.1.1
      interval: 2.0              # Override: ping every 2s
      timeout: 5.0               # Override: 5s timeout
      thresholds:                # Override thresholds
        warning_latency_ms: 200.0
        critical_latency_ms: 1000.0
```

## Usage

### Programmatic Usage
```python
import asyncio
from uptop.collectors.ping_collector import PingCollector
from uptop.plugins.ping_config import PingPluginConfig, PingHostConfig

# Create configuration
config = PingPluginConfig(
    hosts=[
        PingHostConfig(host="example.com"),
        PingHostConfig(host="8.8.8.8"),
        PingHostConfig(
            host="192.168.1.1",
            thresholds=PingThresholds(
                warning_latency_ms=50.0,
                critical_latency_ms=200.0,
            )
        ),
    ],
    concurrent_limit=5,
)

# Create collector
collector = PingCollector(config)

# Collect ping data
async def main():
    data = await collector.collect()
    
    # Access results
    print(f"Total hosts: {data.total_hosts}")
    print(f"Hosts up: {data.hosts_up}")
    print(f"Hosts down: {data.hosts_down}")
    
    for host in data.hosts:
        print(f"\n{host.host}:")
        print(f"  Status: {host.status}")
        print(f"  IP: {host.ip_address}")
        print(f"  Latency: {host.current_latency_ms}ms")
        print(f"  Avg: {host.avg_latency_ms}ms")
        print(f"  Packet Loss: {host.packet_loss_percent}%")
        print(f"  Alert Level: {host.alert_level}")
        print(f"  History: {len(host.history)} measurements")

asyncio.run(main())
```

### Loading from Config File
```python
from uptop.config.loader import load_config

# Load full uptop config
config = load_config()

# Access ping config
ping_config = config.ping

# Create collector
collector = PingCollector(ping_config)
```

## Data Models

### PingMetrics
Single ping measurement:
```python
PingMetrics(
    latency_ms=42.5,      # Latency in milliseconds (None if failed)
    success=True,         # Whether ping succeeded
    timestamp=1234567890.0  # Unix timestamp
)
```

### HostPingResult
Aggregated results for one host:
```python
HostPingResult(
    host="example.com",
    ip_address="93.184.216.34",
    status="up",  # up|down|dns_failed|timeout|disabled|error
    current_latency_ms=42.5,
    min_latency_ms=40.0,
    avg_latency_ms=42.0,
    max_latency_ms=45.0,
    jitter_ms=1.5,
    packet_loss_percent=0.0,
    consecutive_failures=0,
    alert_level="ok",  # ok|warning|critical
    history=[...],  # List of PingMetrics
    last_updated=1234567890.0
)
```

### PingData
Complete ping data:
```python
PingData(
    hosts=[...],      # List of HostPingResult
    total_hosts=3,
    hosts_up=2,
    hosts_down=1
)
```

## Features

### DNS Resolution
- **Caching**: Resolved IPs cached for performance
- **Retry**: Exponential backoff on DNS failures
- **Configurable**: Max attempts and backoff delays

### Ping Execution
- **Platform-specific**: Handles macOS and Linux differences
- **Async**: Non-blocking subprocess execution
- **Timeout**: Configurable per-host timeout
- **Multiple pings**: Sends N pings per check for reliability

### Output Parsing
- **Robust regex**: Handles various ping output formats
- **Latency extraction**: Parses individual ping times
- **Packet loss**: Extracts from statistics line
- **Graceful fallback**: Handles malformed output

### Metrics Calculation
- **Min/Avg/Max**: Calculated from multiple pings
- **Jitter**: Standard deviation of latencies
- **Packet Loss**: Percentage of failed pings

### Alerting
- **Three levels**: ok, warning, critical
- **Dual thresholds**: Latency AND packet loss
- **Per-host**: Override thresholds per host
- **Critical precedence**: Critical overrides warning

### History Buffer
- **Ring buffer**: Fixed size per host
- **Configurable**: Size set in config
- **Efficient**: Old entries automatically dropped

### Error Handling
- **Per-host isolation**: One host failure doesn't affect others
- **Consecutive tracking**: Counts failures per host
- **Auto-disable**: Disables after N consecutive failures
- **Graceful degradation**: Shows errors, continues operation

### Performance
- **Concurrent execution**: Pings hosts in parallel
- **Bounded parallelism**: Semaphore limits concurrent pings
- **Configurable limit**: Max concurrent operations
- **Efficient**: Uses async/await throughout

## Testing

### Run Tests
```bash
# All ping tests
task test tests/test_ping_models.py tests/test_ping_config.py tests/test_ping_collector.py

# Specific test file
task test tests/test_ping_collector.py

# With verbose output
task test tests/test_ping_collector.py -v

# With coverage
task test:coverage
```

### Test Coverage
- **Models**: 100% coverage of validation logic
- **Config**: All config scenarios tested
- **Collector**: 
  - DNS resolution and retry
  - Ping parsing (macOS/Linux formats)
  - Threshold evaluation
  - History management
  - Auto-disable logic
  - Concurrent execution
  - Error handling

### Mocking Strategy
- **DNS**: `socket.gethostbyname` mocked
- **Ping**: `_execute_ping` mocked with sample output
- **No network calls**: All tests run offline

## Platform Support

### macOS
- **Ping path**: `/sbin/ping`
- **Timeout flag**: `-W` (milliseconds)
- **Output format**: Parsed with regex

### Linux
- **Ping path**: `/bin/ping`
- **Timeout flag**: `-W` (seconds)
- **Output format**: Parsed with regex

## Defaults

| Setting | Default | Range |
|---------|---------|-------|
| interval | 1.0s | 0.1s - 3600s |
| timeout | 2.0s | 0.5s+ |
| concurrent_limit | 10 | 1 - 100 |
| pings_per_check | 3 | 1 - 10 |
| history_size | 300 | 10 - 10000 |
| warning_latency_ms | 100.0 | 0+ |
| critical_latency_ms | 500.0 | > warning |
| warning_packet_loss | 5.0% | 0 - 100% |
| critical_packet_loss | 20.0% | > warning |
| dns_max_attempts | 3 | 1 - 10 |
| auto_disable_threshold | 10 | 1+ |

## Status Values

### Host Status
- `up` - Host reachable, ping successful
- `down` - Host unreachable, 100% packet loss
- `dns_failed` - DNS resolution failed
- `timeout` - Ping command timed out
- `disabled` - Auto-disabled after failures
- `error` - Unexpected error occurred

### Alert Levels
- `ok` - All metrics within normal range
- `warning` - Latency or packet loss exceeds warning threshold
- `critical` - Latency or packet loss exceeds critical threshold

## Common Patterns

### Custom Thresholds for Critical Hosts
```yaml
hosts:
  - host: critical-server.example.com
    thresholds:
      warning_latency_ms: 50.0    # Stricter
      critical_latency_ms: 150.0  # Stricter
```

### Higher Tolerance for Remote Hosts
```yaml
hosts:
  - host: remote-site.example.com
    timeout: 5.0
    thresholds:
      warning_latency_ms: 200.0    # More lenient
      critical_latency_ms: 1000.0  # More lenient
```

### Frequent Monitoring
```yaml
hosts:
  - host: api.example.com
    interval: 0.5  # Ping every 500ms
```

### Disable Auto-Disable
```yaml
auto_disable:
  enabled: false  # Never auto-disable hosts
```

## Troubleshooting

### Ping Permission Issues
macOS/Linux may require permissions for ICMP. The collector uses system ping which handles this.

### DNS Resolution Slow
Increase retry attempts or backoff delays:
```yaml
retry_dns:
  max_attempts: 5
  backoff_seconds: [2.0, 4.0, 8.0, 16.0]
```

### Too Many Concurrent Pings
Reduce concurrent limit:
```yaml
concurrent_limit: 5
```

### False Positives on Slow Networks
Increase thresholds:
```yaml
default_thresholds:
  warning_latency_ms: 300.0
  critical_latency_ms: 1000.0
```

## Next Steps

To complete the ping plugin:
1. **TUI Widget** - Visualization with Textual
2. **Plugin Integration** - Register with uptop
3. **CLI Formatters** - JSON/Prometheus output
4. **Documentation** - User guide and examples

See `SPECIFICATION.md` for detailed implementation plan.
