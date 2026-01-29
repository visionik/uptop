# uptop Monitoring Plugins Specification

**Version**: 2.0
**Date**: 2026-01-29
**Status**: Ready for Implementation

## Overview

This specification defines two new plugin additions to the existing uptop system monitoring tool:

1. **Ping Monitoring Plugin**: Network latency and availability monitoring for configured hosts
2. **Remote Hardware Discovery Plugin**: SSH-based hardware inventory and change detection for remote Linux/Windows machines

Both plugins follow uptop's existing plugin architecture and maintain consistency with core design principles: async operation, graceful degradation, plugin-first development, and ≥75% test coverage.

## Project Context

uptop is an existing Python 3.11+ CLI+TUI system monitor with:
- Plugin architecture (PanePlugin, CollectorPlugin, FormatterPlugin, ActionPlugin)
- Dual mode: interactive TUI (Textual) and scriptable CLI (JSON/Markdown/Prometheus output)
- Async architecture using asyncio throughout
- Core panes: CPU, Memory, Processes, Network, Disk
- Configuration via `~/.config/uptop/config.yaml`
- Task-based workflow (Taskfile.yml)
- Quality standards: ≥75% coverage, PEP 8, type hints, conventional commits

## Requirements (RFC2119)

### Ping Monitoring Plugin

#### MUST Requirements

- MUST support configuration via both config file AND CLI arguments (CLI overrides config)
- MUST collect detailed metrics: host, current latency, min/avg/max latency, packet loss %, jitter, status, consecutive failures count
- MUST maintain history buffer of last 300 pings per host (~5 minutes at 1s interval) for sparkline visualization
- MUST use system ping command (`/sbin/ping` on macOS, `/bin/ping` on Linux) via subprocess
- MUST parse ping output using structured parsing (ping flags + summary line parsing)
- MUST implement threshold-based alerts (yellow warning, red critical) for latency and packet loss
- MUST support per-host threshold overrides with global defaults
- MUST retry DNS resolution failures with backoff before marking host unreachable
- MUST distinguish between "DNS failed" vs "host unreachable" in display
- MUST execute ping operations with bounded parallelism (default: 10 concurrent hosts max)
- MUST operate at 1-second default ping interval
- MUST follow uptop plugin API (PanePlugin interface)
- MUST integrate with existing TUI layout system
- MUST support all display modes (MICRO, MINIMIZED, MEDIUM, MAXIMIZED)
- MUST output data in CLI JSON format under top-level "ping" key
- MUST achieve ≥75% test coverage with mocked subprocess calls

#### SHOULD Requirements

- SHOULD support future interactive TUI commands (add/remove hosts via hotkey) - architecture only, not implemented
- SHOULD provide reasonable default thresholds: warning 100ms/5% loss, critical 500ms/20% loss
- SHOULD use 2-second ping timeout by default
- SHOULD send 3 pings per check for reliable statistics
- SHOULD cache successful DNS resolutions and reuse until failure

#### MAY Requirements

- MAY support separate ping intervals per host in future versions

### Remote Hardware Discovery Plugin

#### MUST Requirements

- MUST support SSH connection using `~/.ssh/config` for all connection settings
- MUST use AsyncSSH library for SSH operations (integrates with uptop's async architecture)
- MUST detect comprehensive hardware: CPU, RAM, disks, network interfaces, GPUs, USB devices, PCI devices, SMART disk health, temperatures, fan speeds, power supplies
- MUST support both Linux and Windows remote hosts
- MUST detect hardware changes at device identity level (new/removed devices by serial number or model)
- MUST alert on health status changes (SMART degradation, temperature warnings, etc.)
- MUST persist hardware baseline to `~/.config/uptop/hardware-state.json`
- MUST load from saved state if available, otherwise perform background scan after TUI startup
- MUST support configurable scan intervals per remote host
- MUST use PowerShell over SSH for Windows hardware detection
- MUST use `/sys` filesystem parsing for Linux hardware detection (no special privileges required)
- MUST implement configurable retry policy per host with exponential backoff default
- MUST auto-disable hosts after N consecutive failures (default: 10), require manual re-enable
- MUST support bounded parallelism for SSH operations (default: 5 concurrent connections)
- MUST use strict SSH host key verification (only accept known hosts from `~/.ssh/known_hosts`)
- MUST support SSH agent with fallback to key files
- MUST show partial data when some hardware detection commands fail
- MUST use device serial numbers with fallback to composite key (model+size+bus) for identification
- MUST warn when devices cannot be uniquely identified
- MUST follow uptop plugin API (PanePlugin interface)
- MUST support all display modes (MICRO, MINIMIZED, MEDIUM, MAXIMIZED)
- MUST output data in CLI JSON format under top-level "hardware" key
- MUST achieve ≥75% test coverage with mocked SSH connections

#### SHOULD Requirements

- SHOULD use reasonable defaults: 15-minute scan interval, 10-second SSH timeout, 30-second command timeout
- SHOULD perform initial baseline scan in background after startup (non-blocking)
- SHOULD provide "reset baseline" command to re-establish baseline after intentional changes
- SHOULD retry failed components separately on next scan interval

#### MAY Requirements

- MAY support manual scan trigger via hotkey

### Configuration Management

#### MUST Requirements

- MUST validate configuration on load and disable plugins with invalid config (graceful degradation)
- MUST provide `uptop --validate-config` command to check configuration without starting uptop
- MUST define plugin dependencies as optional extras: `pip install uptop[monitoring]` includes asyncssh
- MUST check for dependencies at runtime and disable plugins with helpful error messages if missing
- MUST inform users how to install missing dependencies

#### SHOULD Requirements

- SHOULD use Pydantic models for configuration validation
- SHOULD provide clear error messages for common configuration mistakes

### Testing Strategy

#### MUST Requirements

- MUST achieve ≥75% test coverage overall AND per-module
- MUST mock external dependencies: subprocess (ping), AsyncSSH connections, file I/O
- MUST test data models, parsers, collectors, configuration loading
- MUST test error handling: connection failures, parsing errors, timeout scenarios
- MUST test threshold logic and alert triggering

#### SHOULD Requirements

- SHOULD include unit tests for all public methods
- SHOULD test edge cases: DNS failures, partial scan failures, SSH key issues

#### MAY Requirements

- MAY include manual integration tests against real targets (not part of automated suite)

### Documentation

#### MUST Requirements

- MUST include comprehensive docstrings (PEP 257) in all code
- MUST update main README.md with plugin features overview
- MUST provide configuration examples for both plugins

#### SHOULD Requirements

- SHOULD document common troubleshooting scenarios
- SHOULD provide example configurations for typical use cases

## Architecture

### Ping Monitoring Plugin Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Ping Pane Plugin                        │
├─────────────────────────────────────────────────────────────┤
│  PingPane(PanePlugin)                                        │
│    ├─ collect_data() → PingData                             │
│    ├─ render_tui(data, size, mode) → Widget                 │
│    └─ get_schema() → type[PingData]                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Ping Collector                            │
├─────────────────────────────────────────────────────────────┤
│  PingCollector(DataCollector)                                │
│    ├─ async collect() → PingData                            │
│    ├─ _ping_host(host) → HostPingResult                     │
│    ├─ _parse_ping_output(output) → PingMetrics              │
│    └─ _resolve_hostname(host) → str (IP)                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Subprocess Execution                      │
├─────────────────────────────────────────────────────────────┤
│  asyncio.create_subprocess_exec()                            │
│    └─ /sbin/ping -c 3 -W 2 <host>                          │
└─────────────────────────────────────────────────────────────┘
```

### Remote Hardware Discovery Plugin Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               Hardware Discovery Pane Plugin                 │
├─────────────────────────────────────────────────────────────┤
│  HardwarePane(PanePlugin)                                    │
│    ├─ collect_data() → HardwareData                         │
│    ├─ render_tui(data, size, mode) → Widget                 │
│    └─ get_schema() → type[HardwareData]                     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                Hardware Discovery Collector                  │
├─────────────────────────────────────────────────────────────┤
│  HardwareCollector(DataCollector)                            │
│    ├─ async collect() → HardwareData                        │
│    ├─ async _scan_host(host) → HostHardware                 │
│    ├─ _compare_with_baseline(host, current) → Changes       │
│    └─ _save_baseline(host, hardware)                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    SSH Connection Layer                      │
├─────────────────────────────────────────────────────────────┤
│  SSHClient (AsyncSSH wrapper)                                │
│    ├─ async connect(host) → Connection                      │
│    ├─ async execute_command(cmd) → stdout                   │
│    └─ respects ~/.ssh/config                                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│            Platform-Specific Detection Commands              │
├─────────────────────────────────────────────────────────────┤
│  Linux: /sys parsing (cpu, memory, disks, network, etc.)    │
│  Windows: PowerShell Get-CimInstance/Get-WmiObject          │
└─────────────────────────────────────────────────────────────┘
```

### Data Models

#### Ping Monitoring Data Models

```python
from pydantic import BaseModel, Field
from uptop.models.base import MetricData, gauge_field, counter_field

class PingMetrics(BaseModel):
    """Single ping measurement."""
    latency_ms: float | None = gauge_field("Latency in milliseconds", default=None, ge=0.0)
    success: bool = Field(..., description="Whether ping succeeded")
    timestamp: float = Field(..., description="Unix timestamp of measurement")

class HostPingResult(BaseModel):
    """Aggregated ping results for a single host."""
    host: str = Field(..., description="Hostname or IP address")
    ip_address: str | None = Field(default=None, description="Resolved IP address")
    status: str = Field(..., description="up|down|dns_failed|timeout")
    current_latency_ms: float | None = gauge_field("Current latency", default=None, ge=0.0)
    min_latency_ms: float | None = gauge_field("Minimum latency", default=None, ge=0.0)
    avg_latency_ms: float | None = gauge_field("Average latency", default=None, ge=0.0)
    max_latency_ms: float | None = gauge_field("Maximum latency", default=None, ge=0.0)
    jitter_ms: float | None = gauge_field("Jitter (stddev)", default=None, ge=0.0)
    packet_loss_percent: float = gauge_field("Packet loss percentage", default=0.0, ge=0.0, le=100.0)
    consecutive_failures: int = counter_field("Consecutive failure count", default=0, ge=0)
    alert_level: str = Field(default="ok", description="ok|warning|critical")
    history: list[PingMetrics] = Field(default_factory=list, description="Recent ping history (max 300)")
    last_updated: float = Field(..., description="Unix timestamp of last update")

class PingData(MetricData):
    """Complete ping monitoring data for all hosts."""
    hosts: list[HostPingResult] = Field(default_factory=list, description="Per-host ping results")
    total_hosts: int = Field(default=0, ge=0, description="Total configured hosts")
    hosts_up: int = Field(default=0, ge=0, description="Number of reachable hosts")
    hosts_down: int = Field(default=0, ge=0, description="Number of unreachable hosts")
```

#### Hardware Discovery Data Models

```python
from pydantic import BaseModel, Field
from uptop.models.base import MetricData

class HardwareDevice(BaseModel):
    """Single hardware device."""
    device_type: str = Field(..., description="cpu|memory|disk|network|gpu|usb|pci|fan|power_supply")
    identifier: str = Field(..., description="Unique device ID (serial or composite)")
    name: str = Field(..., description="Device name/model")
    details: dict[str, Any] = Field(default_factory=dict, description="Device-specific attributes")
    health_status: str | None = Field(default=None, description="healthy|warning|critical|unknown")
    temperature_celsius: float | None = Field(default=None, description="Device temperature if available")

class HardwareChange(BaseModel):
    """Detected hardware change."""
    change_type: str = Field(..., description="added|removed|modified|health_degraded")
    device_type: str = Field(..., description="Type of affected device")
    device_identifier: str = Field(..., description="Unique device ID")
    old_value: dict[str, Any] | None = Field(default=None, description="Previous state")
    new_value: dict[str, Any] | None = Field(default=None, description="New state")
    timestamp: float = Field(..., description="Unix timestamp of detection")

class HostHardware(BaseModel):
    """Hardware inventory for a single remote host."""
    host: str = Field(..., description="Hostname or IP")
    os_type: str = Field(..., description="linux|windows")
    devices: list[HardwareDevice] = Field(default_factory=list, description="Detected devices")
    changes: list[HardwareChange] = Field(default_factory=list, description="Changes since baseline")
    scan_status: str = Field(..., description="success|partial|failed|scanning")
    last_scan: float | None = Field(default=None, description="Unix timestamp of last scan")
    error_message: str | None = Field(default=None, description="Error details if scan failed")

class HardwareData(MetricData):
    """Complete hardware discovery data for all remote hosts."""
    remote_hosts: list[HostHardware] = Field(default_factory=list, description="Per-host hardware data")
    total_hosts: int = Field(default=0, ge=0, description="Total configured hosts")
    hosts_scanned: int = Field(default=0, ge=0, description="Hosts successfully scanned")
    total_changes: int = Field(default=0, ge=0, description="Total detected changes across all hosts")
```

### Configuration Schema

```yaml
# ~/.config/uptop/config.yaml

ping:
  enabled: true
  default_interval: 1.0  # seconds between ping checks
  default_timeout: 2.0   # ping command timeout
  concurrent_limit: 10   # max parallel ping operations
  pings_per_check: 3     # number of pings to send per check
  history_size: 300      # number of results to keep per host
  
  default_thresholds:
    warning_latency_ms: 100
    critical_latency_ms: 500
    warning_packet_loss_percent: 5
    critical_packet_loss_percent: 20
  
  retry_dns:
    enabled: true
    max_attempts: 3
    backoff_seconds: [1, 2, 4]
  
  auto_disable:
    enabled: true
    consecutive_failures_threshold: 10
  
  hosts:
    - host: 192.168.1.1
      # uses all defaults
    
    - host: example.com
      interval: 2.0  # override default interval
      thresholds:
        warning_latency_ms: 200  # override for this host
        critical_latency_ms: 1000

hardware:
  enabled: true
  default_scan_interval: 900  # 15 minutes in seconds
  concurrent_limit: 5         # max parallel SSH connections
  ssh_timeout: 10             # SSH connection timeout
  command_timeout: 30         # remote command timeout
  state_file: ~/.config/uptop/hardware-state.json
  
  retry_policy:
    max_attempts: 3
    backoff_type: exponential  # exponential|fixed
    initial_backoff_seconds: 2
  
  auto_disable:
    enabled: true
    consecutive_failures_threshold: 10
  
  detection:
    linux:
      use_sys_filesystem: true
      detect_smart: true
      detect_temperatures: true
    windows:
      use_powershell: true
      use_cim: true  # prefer Get-CimInstance
  
  remote_hosts:
    - host: server1.example.com
      scan_interval: 600  # 10 minutes for this host
      # SSH config from ~/.ssh/config
    
    - host: 192.168.1.100
      os_type: linux  # optional hint
      scan_interval: 1800  # 30 minutes
      retry_policy:
        max_attempts: 5  # override for flaky host
```

## Implementation Plan

### Phase 1: Ping Monitoring Plugin (MVP)

This phase completes a fully functional ping monitoring plugin end-to-end.

#### Subphase 1.1: Data Models and Configuration
**Dependencies**: None
**Estimated effort**: 2-3 hours

- **Task 1.1.1**: Create `src/uptop/plugins/ping_models.py`
  - Define `PingMetrics`, `HostPingResult`, `PingData` Pydantic models
  - Add metric type annotations (gauge_field, counter_field)
  - Acceptance: Models validate correctly, pass ≥75% coverage

- **Task 1.1.2**: Create `src/uptop/plugins/ping_config.py`
  - Define `PingHostConfig`, `PingPluginConfig` models
  - Implement config validation logic
  - Acceptance: Valid configs load, invalid configs raise ValidationError

- **Task 1.1.3**: Add ping config schema to main config
  - Update `src/uptop/config/loader.py` to include ping section
  - Add default config values
  - Acceptance: Ping config loads from YAML, merges with defaults

- **Task 1.1.4**: Tests for models and config
  - Create `tests/test_ping_models.py`
  - Create `tests/test_ping_config.py`
  - Test validation, defaults, overrides
  - Acceptance: ≥75% coverage

#### Subphase 1.2: Ping Collector (depends on: 1.1)
**Dependencies**: Subphase 1.1
**Estimated effort**: 4-6 hours

- **Task 1.2.1**: Create `src/uptop/collectors/ping_collector.py`
  - Implement `PingCollector(DataCollector[PingData])`
  - Stub `async collect()` method
  - Acceptance: Collector instantiates, inherits from DataCollector

- **Task 1.2.2**: Implement DNS resolution with retry
  - Add `_resolve_hostname(host)` with exponential backoff
  - Cache successful resolutions
  - Acceptance: DNS resolution works, retries on failure, caches results

- **Task 1.2.3**: Implement ping execution
  - Add `_execute_ping(host, count, timeout)` using `asyncio.create_subprocess_exec`
  - Detect OS and use correct ping command (/sbin/ping vs /bin/ping)
  - Acceptance: Subprocess executes ping, returns stdout/stderr

- **Task 1.2.4**: Implement ping output parser
  - Add `_parse_ping_output(output, os_type)` with structured parsing
  - Extract latency, packet loss from summary lines
  - Handle macOS and Linux output format differences
  - Acceptance: Parser extracts metrics from real ping output samples

- **Task 1.2.5**: Implement `_ping_host(host_config)`
  - Combine DNS resolution + ping execution + parsing
  - Calculate min/avg/max/jitter from multiple pings
  - Handle errors gracefully (DNS failure, timeout, parse error)
  - Acceptance: Returns `HostPingResult` with all metrics

- **Task 1.2.6**: Implement threshold evaluation
  - Add `_evaluate_thresholds(result, thresholds)` 
  - Set alert_level based on latency and packet loss
  - Acceptance: Alert levels set correctly based on thresholds

- **Task 1.2.7**: Implement history buffer management
  - Add `_update_history(host, new_metric)` 
  - Maintain ring buffer of max 300 entries per host
  - Acceptance: History maintains correct size, oldest entries dropped

- **Task 1.2.8**: Implement full `collect()` method
  - Gather all configured hosts
  - Execute pings with bounded parallelism (asyncio.Semaphore)
  - Update history buffers
  - Track consecutive failures
  - Return complete `PingData`
  - Acceptance: Collects data for multiple hosts in parallel

- **Task 1.2.9**: Tests for ping collector
  - Create `tests/test_ping_collector.py`
  - Mock subprocess calls
  - Test DNS resolution, parsing, threshold logic, parallelism
  - Test error handling: DNS failure, timeout, parse errors
  - Acceptance: ≥75% coverage

- **Task 1.2.10**: Run `task check`
  - Ensure fmt, lint, type check, tests all pass
  - Acceptance: All checks pass

#### Subphase 1.3: Ping TUI Widget (depends on: 1.2)
**Dependencies**: Subphase 1.2
**Estimated effort**: 4-5 hours

- **Task 1.3.1**: Create `src/uptop/tui/widgets/ping_widget.py`
  - Implement `PingWidget(Widget)` for rendering ping data
  - Support all display modes (MICRO, MINIMIZED, MEDIUM, MAXIMIZED)
  - Acceptance: Widget renders basic structure

- **Task 1.3.2**: Implement MICRO mode display
  - Show: "Ping: X/Y hosts up"
  - Acceptance: Compact one-line summary

- **Task 1.3.3**: Implement MINIMIZED mode display
  - Show table: host, status (up/down), current latency
  - Color-code by alert level (green/yellow/red)
  - Acceptance: Minimal table with status indicators

- **Task 1.3.4**: Implement MEDIUM mode display
  - Show table: host, status, latency (cur/avg/max), packet loss, alert
  - Include sparkline for latency history
  - Acceptance: Detailed table with sparklines

- **Task 1.3.5**: Implement MAXIMIZED mode display
  - Show all MEDIUM content
  - Add jitter, consecutive failures, last updated timestamp
  - Larger sparklines
  - Acceptance: Full detailed view

- **Task 1.3.6**: Tests for ping widget
  - Create `tests/test_ping_widget.py`
  - Test rendering in each display mode
  - Test with different alert levels
  - Acceptance: ≥75% coverage

- **Task 1.3.7**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 1.4: Ping Pane Plugin Integration (depends on: 1.3)
**Dependencies**: Subphase 1.3
**Estimated effort**: 3-4 hours

- **Task 1.4.1**: Create `src/uptop/plugins/ping.py`
  - Implement `PingPane(PanePlugin)`
  - Wire `collect_data()` to `PingCollector`
  - Wire `render_tui()` to `PingWidget`
  - Implement `get_schema()` returning `PingData`
  - Acceptance: Plugin follows PanePlugin interface

- **Task 1.4.2**: Register plugin in plugin registry
  - Add to `src/uptop/plugins/__init__.py` exports
  - Register as internal plugin in registry
  - Acceptance: Plugin discovered by registry

- **Task 1.4.3**: Add plugin to TUI app
  - Update `src/uptop/tui/app.py` to include ping pane
  - Position in layout (suggest: bottom row with network/disk)
  - Acceptance: Ping pane appears in TUI

- **Task 1.4.4**: Tests for ping plugin
  - Create `tests/test_ping_plugin.py`
  - Test plugin lifecycle (init, collect, render, shutdown)
  - Test with mocked collector
  - Acceptance: ≥75% coverage

- **Task 1.4.5**: Manual TUI testing
  - Run `uptop` with ping config
  - Verify pane displays correctly
  - Test display mode switching
  - Test with unreachable hosts, DNS failures
  - Acceptance: TUI works as expected

- **Task 1.4.6**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 1.5: Ping CLI Output (depends on: 1.4)
**Dependencies**: Subphase 1.4
**Estimated effort**: 2-3 hours

- **Task 1.5.1**: Update JSON formatter
  - Modify `src/uptop/formatters/json_formatter.py` to include ping data
  - Add ping data under top-level "ping" key
  - Acceptance: `uptop --json --once` includes ping section

- **Task 1.5.2**: Update Prometheus formatter
  - Modify `src/uptop/formatters/prometheus.py` to include ping metrics
  - Generate metrics: `uptop_ping_latency_ms{host="..."}`, `uptop_ping_packet_loss_percent{host="..."}`, etc.
  - Acceptance: `uptop --prometheus` includes ping metrics

- **Task 1.5.3**: Tests for CLI output
  - Update `tests/test_json_formatter.py`
  - Update `tests/test_prometheus_formatter.py`
  - Acceptance: ≥75% coverage

- **Task 1.5.4**: Manual CLI testing
  - Run `uptop --json --once`
  - Run `uptop --prometheus`
  - Verify ping data in output
  - Acceptance: CLI output correct

- **Task 1.5.5**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 1.6: Documentation and Polish (depends on: 1.5)
**Dependencies**: Subphase 1.5
**Estimated effort**: 2-3 hours

- **Task 1.6.1**: Update README.md
  - Add ping monitoring to features list
  - Add basic usage example
  - Acceptance: README describes ping plugin

- **Task 1.6.2**: Add configuration examples
  - Create example config in README or docs/
  - Show basic and advanced ping configurations
  - Acceptance: Users can copy-paste working config

- **Task 1.6.3**: Add docstrings and code comments
  - Ensure all public methods have PEP 257 docstrings
  - Add inline comments for complex logic (ping parsing)
  - Acceptance: Code is well-documented

- **Task 1.6.4**: Final testing and bug fixes
  - Run full test suite: `task test`
  - Run coverage: `task test:coverage`
  - Fix any discovered issues
  - Acceptance: ≥75% coverage, all tests pass

- **Task 1.6.5**: Git commit
  - Commit with message: `feat(plugins): add ping monitoring plugin`
  - Acceptance: Clean commit following conventional commits

### Phase 2: Remote Hardware Discovery Plugin

This phase completes the hardware discovery plugin end-to-end.

#### Subphase 2.1: SSH Infrastructure (depends on: Phase 1)
**Dependencies**: Phase 1 complete
**Estimated effort**: 4-5 hours

- **Task 2.1.1**: Add AsyncSSH dependency
  - Update `pyproject.toml` with optional dependency: `monitoring = ["asyncssh>=2.14.0"]`
  - Update dependency check in plugin
  - Acceptance: `pip install uptop[monitoring]` installs asyncssh

- **Task 2.1.2**: Create `src/uptop/utils/ssh_client.py`
  - Implement `SSHClient` wrapper around AsyncSSH
  - Support SSH config file (`~/.ssh/config`) integration
  - Support SSH agent with fallback to key files
  - Implement strict host key checking
  - Acceptance: Client connects via SSH respecting config

- **Task 2.1.3**: Implement connection pooling
  - Add `SSHConnectionPool` for reusing connections
  - Implement connection timeout and keepalive
  - Acceptance: Connections reused efficiently

- **Task 2.1.4**: Implement command execution
  - Add `async execute_command(host, cmd, timeout)` 
  - Return stdout, stderr, exit code
  - Handle timeouts gracefully
  - Acceptance: Commands execute remotely, results returned

- **Task 2.1.5**: Tests for SSH client
  - Create `tests/test_ssh_client.py`
  - Mock AsyncSSH connections
  - Test connection, command execution, error handling
  - Acceptance: ≥75% coverage

- **Task 2.1.6**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.2: Hardware Detection - Linux (depends on: 2.1)
**Dependencies**: Subphase 2.1
**Estimated effort**: 6-8 hours

- **Task 2.2.1**: Create `src/uptop/collectors/hardware/linux_detector.py`
  - Implement `LinuxHardwareDetector` class
  - Acceptance: Class structure in place

- **Task 2.2.2**: Implement CPU detection
  - Parse `/sys/devices/system/cpu/` via SSH
  - Extract CPU model, cores, frequency
  - Acceptance: Returns CPU device info

- **Task 2.2.3**: Implement memory detection
  - Parse `/sys/devices/system/memory/` or `/proc/meminfo`
  - Extract total RAM, modules if available
  - Acceptance: Returns memory device info

- **Task 2.2.4**: Implement disk detection
  - Parse `/sys/block/` for block devices
  - Use `lsblk -J` if available for structured output
  - Extract disk model, size, serial
  - Acceptance: Returns disk device list

- **Task 2.2.5**: Implement SMART health detection
  - Execute `smartctl -a /dev/sdX` if available
  - Parse SMART health status
  - Acceptance: Returns disk health status

- **Task 2.2.6**: Implement network interface detection
  - Parse `/sys/class/net/`
  - Extract interface name, MAC, link status
  - Acceptance: Returns network interface list

- **Task 2.2.7**: Implement GPU detection
  - Use `lspci` to detect GPUs if available
  - Parse `/sys/class/drm/` for additional info
  - Acceptance: Returns GPU device list

- **Task 2.2.8**: Implement USB device detection
  - Parse `/sys/bus/usb/devices/`
  - Extract USB device vendor, product, serial
  - Acceptance: Returns USB device list

- **Task 2.2.9**: Implement temperature sensor detection
  - Parse `/sys/class/hwmon/`
  - Extract temperature readings
  - Acceptance: Returns temperature data

- **Task 2.2.10**: Implement fan speed detection
  - Parse `/sys/class/hwmon/` fan inputs
  - Acceptance: Returns fan speed data

- **Task 2.2.11**: Aggregate all detectors
  - Implement `async detect_all_hardware(ssh_client, host)` 
  - Call all detection methods
  - Handle partial failures (show what succeeded)
  - Return `list[HardwareDevice]`
  - Acceptance: Complete hardware inventory returned

- **Task 2.2.12**: Tests for Linux detector
  - Create `tests/test_linux_detector.py`
  - Mock SSH command execution with sample /sys outputs
  - Test each detection method
  - Test partial failure handling
  - Acceptance: ≥75% coverage

- **Task 2.2.13**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.3: Hardware Detection - Windows (depends on: 2.1)
**Dependencies**: Subphase 2.1
**Estimated effort**: 5-7 hours

- **Task 2.3.1**: Create `src/uptop/collectors/hardware/windows_detector.py`
  - Implement `WindowsHardwareDetector` class
  - Acceptance: Class structure in place

- **Task 2.3.2**: Implement PowerShell command execution
  - Add `_execute_powershell(ssh_client, host, script)` helper
  - Handle PowerShell output parsing (ConvertTo-Json)
  - Acceptance: PowerShell commands execute via SSH

- **Task 2.3.3**: Implement CPU detection
  - Use `Get-CimInstance Win32_Processor`
  - Extract CPU model, cores, frequency
  - Acceptance: Returns CPU device info

- **Task 2.3.4**: Implement memory detection
  - Use `Get-CimInstance Win32_PhysicalMemory`
  - Extract RAM modules, capacity, speed
  - Acceptance: Returns memory device list

- **Task 2.3.5**: Implement disk detection
  - Use `Get-CimInstance Win32_DiskDrive`
  - Extract disk model, size, serial
  - Acceptance: Returns disk device list

- **Task 2.3.6**: Implement SMART health detection (if available)
  - Use `Get-StorageReliabilityCounter` or WMI
  - Parse health status
  - Acceptance: Returns disk health status

- **Task 2.3.7**: Implement network adapter detection
  - Use `Get-CimInstance Win32_NetworkAdapter`
  - Extract adapter name, MAC, status
  - Acceptance: Returns network interface list

- **Task 2.3.8**: Implement GPU detection
  - Use `Get-CimInstance Win32_VideoController`
  - Extract GPU model, memory
  - Acceptance: Returns GPU device list

- **Task 2.3.9**: Implement USB device detection
  - Use `Get-CimInstance Win32_PnPEntity` filtered by USB
  - Acceptance: Returns USB device list

- **Task 2.3.10**: Implement temperature sensor detection
  - Use WMI thermal sensors if available
  - Acceptance: Returns temperature data or graceful N/A

- **Task 2.3.11**: Aggregate all detectors
  - Implement `async detect_all_hardware(ssh_client, host)` 
  - Call all detection methods
  - Handle partial failures
  - Return `list[HardwareDevice]`
  - Acceptance: Complete hardware inventory returned

- **Task 2.3.12**: Tests for Windows detector
  - Create `tests/test_windows_detector.py`
  - Mock SSH PowerShell execution with sample outputs
  - Test each detection method
  - Acceptance: ≥75% coverage

- **Task 2.3.13**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.4: Hardware Data Models and Baseline (depends on: 2.2, 2.3)
**Dependencies**: Subphases 2.2, 2.3
**Estimated effort**: 4-5 hours

- **Task 2.4.1**: Create `src/uptop/plugins/hardware_models.py`
  - Define `HardwareDevice`, `HardwareChange`, `HostHardware`, `HardwareData` models
  - Acceptance: Models validate correctly

- **Task 2.4.2**: Implement device identification logic
  - Add `_get_device_identifier(device)` 
  - Use serial if available, fall back to composite key
  - Acceptance: Devices have stable unique IDs

- **Task 2.4.3**: Implement baseline persistence
  - Create `src/uptop/collectors/hardware/baseline.py`
  - Implement `save_baseline(host, devices, state_file)` 
  - Implement `load_baseline(host, state_file)` 
  - Use JSON format for state file
  - Acceptance: Baseline saved/loaded correctly

- **Task 2.4.4**: Implement change detection
  - Implement `compare_hardware(baseline, current)` 
  - Detect added/removed/modified devices
  - Detect health status changes
  - Return `list[HardwareChange]`
  - Acceptance: Changes detected correctly

- **Task 2.4.5**: Tests for models and baseline
  - Create `tests/test_hardware_models.py`
  - Create `tests/test_hardware_baseline.py`
  - Test identification, persistence, change detection
  - Acceptance: ≥75% coverage

- **Task 2.4.6**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.5: Hardware Collector (depends on: 2.4)
**Dependencies**: Subphase 2.4
**Estimated effort**: 5-6 hours

- **Task 2.5.1**: Create `src/uptop/collectors/hardware_collector.py`
  - Implement `HardwareCollector(DataCollector[HardwareData])`
  - Stub `async collect()` method
  - Acceptance: Collector instantiates

- **Task 2.5.2**: Implement OS detection
  - Add `_detect_os_type(ssh_client, host)` 
  - Use `uname` for Linux, check for PowerShell for Windows
  - Acceptance: Returns "linux" or "windows"

- **Task 2.5.3**: Implement `_scan_host(host_config)` 
  - Connect via SSH
  - Detect OS type
  - Call appropriate detector (Linux or Windows)
  - Load baseline if exists
  - Compare and detect changes
  - Save new baseline
  - Return `HostHardware`
  - Handle connection failures, command failures
  - Acceptance: Single host scanned correctly

- **Task 2.5.4**: Implement retry logic with exponential backoff
  - Add `_scan_with_retry(host_config)` 
  - Retry based on host's retry policy
  - Acceptance: Retries on failure with backoff

- **Task 2.5.5**: Implement auto-disable logic
  - Track consecutive failures per host
  - Disable host after threshold reached
  - Acceptance: Hosts auto-disabled after N failures

- **Task 2.5.6**: Implement full `collect()` method
  - Gather all configured hosts
  - Execute scans with bounded parallelism (asyncio.Semaphore)
  - Track scan status per host
  - Return complete `HardwareData`
  - Acceptance: Collects data for multiple hosts in parallel

- **Task 2.5.7**: Implement background initial scan
  - Add flag to skip blocking wait on first scan
  - Start scans in background tasks
  - Update data as scans complete
  - Acceptance: TUI responsive during initial scan

- **Task 2.5.8**: Tests for hardware collector
  - Create `tests/test_hardware_collector.py`
  - Mock SSH connections and command outputs
  - Test OS detection, scanning, retry logic, parallelism
  - Test error handling: connection failure, partial failure
  - Acceptance: ≥75% coverage

- **Task 2.5.9**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.6: Hardware TUI Widget (depends on: 2.5)
**Dependencies**: Subphase 2.5
**Estimated effort**: 4-5 hours

- **Task 2.6.1**: Create `src/uptop/tui/widgets/hardware_widget.py`
  - Implement `HardwareWidget(Widget)` for rendering hardware data
  - Support all display modes (MICRO, MINIMIZED, MEDIUM, MAXIMIZED)
  - Acceptance: Widget renders basic structure

- **Task 2.6.2**: Implement MICRO mode display
  - Show: "Hardware: X hosts, Y changes"
  - Acceptance: Compact one-line summary

- **Task 2.6.3**: Implement MINIMIZED mode display
  - Show table: host, status (scanned/scanning/failed), device count, change count
  - Highlight hosts with changes
  - Acceptance: Minimal table with status

- **Task 2.6.4**: Implement MEDIUM mode display
  - Show table: host, status, devices by type (CPU/RAM/Disk/etc counts), changes
  - List changes with type and device identifier
  - Color-code: green=added, red=removed, yellow=modified/health_degraded
  - Acceptance: Detailed table with change summary

- **Task 2.6.5**: Implement MAXIMIZED mode display
  - Show all MEDIUM content
  - Expand change details (old value → new value)
  - Show last scan timestamp
  - Show error messages for failed scans
  - Acceptance: Full detailed view

- **Task 2.6.6**: Tests for hardware widget
  - Create `tests/test_hardware_widget.py`
  - Test rendering in each display mode
  - Test with changes, errors, scanning status
  - Acceptance: ≥75% coverage

- **Task 2.6.7**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.7: Hardware Pane Plugin Integration (depends on: 2.6)
**Dependencies**: Subphase 2.6
**Estimated effort**: 3-4 hours

- **Task 2.7.1**: Create `src/uptop/plugins/hardware.py`
  - Implement `HardwarePane(PanePlugin)`
  - Wire `collect_data()` to `HardwareCollector`
  - Wire `render_tui()` to `HardwareWidget`
  - Implement `get_schema()` returning `HardwareData`
  - Add dependency check for asyncssh
  - Acceptance: Plugin follows PanePlugin interface

- **Task 2.7.2**: Register plugin in plugin registry
  - Add to `src/uptop/plugins/__init__.py` exports
  - Register as internal plugin
  - Acceptance: Plugin discovered by registry

- **Task 2.7.3**: Add plugin to TUI app
  - Update `src/uptop/tui/app.py` to include hardware pane
  - Position in layout (suggest: separate row or alongside ping)
  - Acceptance: Hardware pane appears in TUI

- **Task 2.7.4**: Tests for hardware plugin
  - Create `tests/test_hardware_plugin.py`
  - Test plugin lifecycle
  - Test with mocked collector and SSH
  - Test dependency check (missing asyncssh)
  - Acceptance: ≥75% coverage

- **Task 2.7.5**: Manual TUI testing
  - Run `uptop` with hardware config
  - Verify pane displays correctly
  - Test display mode switching
  - Test with unreachable hosts, SSH failures
  - Add/remove a USB device and verify change detection
  - Acceptance: TUI works as expected

- **Task 2.7.6**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.8: Hardware CLI Output (depends on: 2.7)
**Dependencies**: Subphase 2.7
**Estimated effort**: 2-3 hours

- **Task 2.8.1**: Update JSON formatter
  - Modify `src/uptop/formatters/json_formatter.py` to include hardware data
  - Add hardware data under top-level "hardware" key
  - Acceptance: `uptop --json --once` includes hardware section

- **Task 2.8.2**: Update Prometheus formatter
  - Modify `src/uptop/formatters/prometheus.py` to include hardware metrics
  - Generate metrics: `uptop_hardware_device_count{host="...",type="..."}`, `uptop_hardware_changes_total{host="..."}`, etc.
  - Acceptance: `uptop --prometheus` includes hardware metrics

- **Task 2.8.3**: Tests for CLI output
  - Update `tests/test_json_formatter.py`
  - Update `tests/test_prometheus_formatter.py`
  - Acceptance: ≥75% coverage

- **Task 2.8.4**: Manual CLI testing
  - Run `uptop --json --once`
  - Run `uptop --prometheus`
  - Verify hardware data in output
  - Acceptance: CLI output correct

- **Task 2.8.5**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.9: Configuration and Validation (depends on: 2.8)
**Dependencies**: Subphase 2.8
**Estimated effort**: 3-4 hours

- **Task 2.9.1**: Create `src/uptop/plugins/hardware_config.py`
  - Define `HardwareHostConfig`, `HardwarePluginConfig` models
  - Implement config validation
  - Acceptance: Valid configs load, invalid configs raise ValidationError

- **Task 2.9.2**: Add hardware config schema to main config
  - Update `src/uptop/config/loader.py` to include hardware section
  - Add default config values
  - Acceptance: Hardware config loads from YAML

- **Task 2.9.3**: Implement `uptop --validate-config` command
  - Add CLI flag in `src/uptop/cli.py`
  - Load config and run validation
  - Report errors with helpful messages
  - Exit 0 if valid, 1 if invalid
  - Acceptance: Command validates config without starting uptop

- **Task 2.9.4**: Tests for config validation
  - Create `tests/test_hardware_config.py`
  - Test valid and invalid configurations
  - Test validation command
  - Acceptance: ≥75% coverage

- **Task 2.9.5**: Run `task check`
  - Acceptance: All checks pass

#### Subphase 2.10: Documentation and Polish (depends on: 2.9)
**Dependencies**: Subphase 2.9
**Estimated effort**: 3-4 hours

- **Task 2.10.1**: Update README.md
  - Add hardware discovery to features list
  - Add basic usage example
  - Document SSH requirements
  - Acceptance: README describes hardware plugin

- **Task 2.10.2**: Add configuration examples
  - Show basic and advanced hardware configurations
  - Document SSH config integration
  - Provide troubleshooting tips (SSH keys, known_hosts, etc.)
  - Acceptance: Users can copy-paste working config

- **Task 2.10.3**: Add docstrings and code comments
  - Ensure all public methods have PEP 257 docstrings
  - Add inline comments for complex logic (detection parsers)
  - Acceptance: Code is well-documented

- **Task 2.10.4**: Update pyproject.toml
  - Ensure monitoring extras documented
  - Add asyncssh to optional dependencies
  - Acceptance: Installation instructions clear

- **Task 2.10.5**: Final testing and bug fixes
  - Run full test suite: `task test`
  - Run coverage: `task test:coverage`
  - Test both plugins together
  - Fix any discovered issues
  - Acceptance: ≥75% coverage, all tests pass

- **Task 2.10.6**: Git commit
  - Commit with message: `feat(plugins): add remote hardware discovery plugin`
  - Acceptance: Clean commit following conventional commits

### Phase 3: Integration Testing and Final Polish

**Dependencies**: Phase 1 and Phase 2 complete
**Estimated effort**: 2-3 hours

#### Subphase 3.1: End-to-End Testing
**Dependencies**: All previous phases
**Estimated effort**: 2-3 hours

- **Task 3.1.1**: Integration test scenarios
  - Create `tests/integration/test_monitoring_plugins.py`
  - Test both plugins running together
  - Test config validation command
  - Test CLI output with both plugins
  - Acceptance: Integration tests pass

- **Task 3.1.2**: Performance testing
  - Test with 20+ ping hosts
  - Test with 5+ remote hardware hosts
  - Verify bounded parallelism works
  - Verify memory usage reasonable
  - Acceptance: Performance within acceptable limits

- **Task 3.1.3**: Final manual testing
  - Run uptop with full config (all panes including new ones)
  - Test display mode switching
  - Test configuration validation
  - Test error scenarios
  - Acceptance: Everything works smoothly

- **Task 3.1.4**: Update project documentation
  - Update main README with both plugins
  - Add examples to docs/ if needed
  - Acceptance: Documentation complete

- **Task 3.1.5**: Final `task check`
  - Ensure all tests pass
  - Ensure coverage ≥75% overall and per-module
  - Ensure no linting/type errors
  - Acceptance: All checks pass

- **Task 3.1.6**: Final git commit
  - Commit any remaining polish
  - Ensure clean git history
  - Acceptance: Ready for merge/release

## Default Configuration Values

### Ping Monitoring Defaults
```python
PING_DEFAULTS = {
    "interval": 1.0,  # 1 second between checks
    "timeout": 2.0,  # 2 second ping timeout
    "pings_per_check": 3,  # send 3 pings per check
    "concurrent_limit": 10,  # max 10 parallel operations
    "history_size": 300,  # 5 minutes at 1s interval
    "thresholds": {
        "warning_latency_ms": 100,
        "critical_latency_ms": 500,
        "warning_packet_loss_percent": 5,
        "critical_packet_loss_percent": 20,
    },
    "retry_dns": {
        "enabled": True,
        "max_attempts": 3,
        "backoff_seconds": [1, 2, 4],
    },
    "auto_disable": {
        "enabled": True,
        "consecutive_failures_threshold": 10,
    },
}
```

### Hardware Discovery Defaults
```python
HARDWARE_DEFAULTS = {
    "scan_interval": 900,  # 15 minutes
    "ssh_timeout": 10,  # 10 second connection timeout
    "command_timeout": 30,  # 30 second command timeout
    "concurrent_limit": 5,  # max 5 parallel SSH connections
    "state_file": "~/.config/uptop/hardware-state.json",
    "retry_policy": {
        "max_attempts": 3,
        "backoff_type": "exponential",
        "initial_backoff_seconds": 2,
    },
    "auto_disable": {
        "enabled": True,
        "consecutive_failures_threshold": 10,
    },
    "detection": {
        "linux": {
            "use_sys_filesystem": True,
            "detect_smart": True,
            "detect_temperatures": True,
        },
        "windows": {
            "use_powershell": True,
            "use_cim": True,
        },
    },
}
```

## Dependencies

### New Dependencies

```toml
[project.optional-dependencies]
monitoring = [
    "asyncssh>=2.14.0",  # SSH client for hardware discovery
]
```

### Existing Dependencies (no changes)
- psutil>=5.9
- textual[dev]>=0.40
- typer[all]>=0.9
- pydantic>=2.0
- PyYAML>=6.0

## Success Criteria

### Ping Monitoring Plugin
- ✓ Plugin discovers and registers successfully
- ✓ Config loads from YAML with validation
- ✓ Pings execute via system ping command
- ✓ Metrics collected: latency, packet loss, jitter, status
- ✓ History buffer maintains 300 entries per host
- ✓ Thresholds evaluated correctly (warning/critical)
- ✓ TUI displays ping data in all display modes
- ✓ Sparklines show latency trends
- ✓ CLI outputs JSON and Prometheus formats
- ✓ DNS resolution retries with backoff
- ✓ Hosts auto-disable after consecutive failures
- ✓ Test coverage ≥75%

### Hardware Discovery Plugin
- ✓ Plugin discovers and registers successfully
- ✓ AsyncSSH dependency check works (graceful disable if missing)
- ✓ SSH connections via ~/.ssh/config
- ✓ SSH agent support with key file fallback
- ✓ Strict host key verification enforced
- ✓ Linux hardware detection via /sys parsing
- ✓ Windows hardware detection via PowerShell
- ✓ Comprehensive device types detected (CPU, RAM, disk, network, GPU, USB, temps, fans)
- ✓ Device identification with serial + fallback
- ✓ Baseline persistence to state file
- ✓ Change detection (added/removed/modified/health)
- ✓ Partial scan results displayed
- ✓ Per-host scan intervals configurable
- ✓ Retry logic with exponential backoff
- ✓ Hosts auto-disable after consecutive failures
- ✓ TUI displays hardware data in all display modes
- ✓ CLI outputs JSON and Prometheus formats
- ✓ Test coverage ≥75%

### General
- ✓ Both plugins work together without conflicts
- ✓ `uptop --validate-config` command works
- ✓ README updated with plugin documentation
- ✓ Configuration examples provided
- ✓ All tests pass: `task check`
- ✓ Code follows project standards (PEP 8, type hints, docstrings)
- ✓ Conventional commits used

## Risk Mitigation

### Ping Parsing Brittleness
**Risk**: Ping output format varies across OS versions
**Mitigation**: Test with multiple OS versions, implement robust regex patterns, graceful fallback for parse failures

### SSH Connection Failures
**Risk**: SSH auth issues, network problems, host key changes
**Mitigation**: Comprehensive error handling, retry logic, clear error messages, respect SSH config

### Performance with Many Hosts
**Risk**: Too many concurrent operations overwhelm system
**Mitigation**: Bounded parallelism with Semaphore, configurable limits, auto-disable failing hosts

### Privilege Requirements
**Risk**: Some hardware info requires root/sudo
**Mitigation**: Use privilege-free detection methods (/sys on Linux), graceful degradation, document limitations

### Test Coverage
**Risk**: External dependencies make testing difficult
**Mitigation**: Extensive mocking of subprocess/SSH, test with realistic sample data

## Appendix: Interview Questions and Answers

**Q1**: How should users specify which servers to ping-monitor?
**A**: Option 3 - Both config file AND CLI (CLI overrides config) with possible support for interactive TUI commands in the future

**Q2**: Which ping metrics are most important?
**A**: Option 3 - Detailed (current latency, min/avg/max, packet loss %, jitter, history for sparklines, consecutive failures)

**Q3**: How should the plugin perform ping operations?
**A**: Option 1 - System ping command (subprocess calling /bin/ping or /sbin/ping)

**Q4**: What alerting behavior do you want?
**A**: Option 3 - Threshold-based alerts (yellow warning, red critical based on latency/packet loss)

**Q5**: Should alert thresholds be configurable per-host or globally?
**A**: Option 2 - Per-host with global defaults

**Q6**: What SSH connection approach should be used?
**A**: Option 3 - SSH config integration (use ~/.ssh/config for all connection settings)

**Q7**: What types of hardware should be detected?
**A**: Option 4 - Comprehensive (CPU, RAM, disks, network, GPUs, USB, PCI, SMART, temps, fans, power supplies)

**Q8**: What types of hardware changes should trigger alerts?
**A**: Option 4 - Health status changes (device identity + health degradation alerts)

**Q9**: How should alerts be displayed and persisted?
**A**: Option 2 - Persistent state file (save hardware baseline to JSON, compare on each check)

**Q10**: How frequently should hardware be scanned?
**A**: Option 5 - Configurable per-host (different intervals for different machines)

**Q11**: Which SSH library should be used?
**A**: Option 2 - AsyncSSH (async/await native, integrates with uptop's architecture)

**Q12**: How should the plugin handle Windows remote hosts?
**A**: Option 1 - PowerShell over SSH (execute PowerShell commands via SSH)

**Q13**: How should connection/command failures be handled?
**A**: Option 5 - Configurable retry policy (let users choose retry behavior per-host)

**Q14**: How should the new panes be laid out in the TUI?
**A**: Option 1 - Separate panes (ping and hardware as independent panels)

**Q15**: For CLI output, how should the data be structured?
**A**: Option 1 - Top-level plugin sections (JSON with "ping" and "hardware" at root level)

**Q16**: How much ping history should be kept?
**A**: Option 3 - Medium (last 300 pings per host, ~5 minutes of history)

**Q17**: When should initial hardware baseline be established?
**A**: Option 4 - Load from saved state (if state file exists, use it; otherwise background scan) [UPDATED from Option 2]

**Q18**: What level of test coverage should be implemented?
**A**: Option 2 - Standard coverage (unit tests + mocked external calls, ≥75% threshold)

**Q19**: How should ping command output be parsed?
**A**: Option 2 - Structured output parsing (use ping flags, parse summary line)

**Q20**: How should devices be uniquely identified?
**A**: Option 3 - Serial + fallback to composite key (serial if available, otherwise model+size+bus)

**Q21**: How should invalid configuration be handled?
**A**: Option 2 + 5 - Disable invalid plugins + validation command (graceful degradation + --validate-config)

**Q22**: How should plugin dependencies be managed?
**A**: Option 4 - Optional dependencies + runtime checks (extras for install + runtime checks with helpful errors) [UPDATED from Option 2]

**Q23**: Which Linux commands/tools should be used?
**A**: Option 2 - /sys filesystem parsing (no special privileges required)

**Q24**: How should concurrent operations be managed?
**A**: Option 2 - Parallel with limit (concurrent operations limited to N hosts at once)

**Q25**: How should the plugins be developed and integrated?
**A**: Option 3 - Ping MVP first (basic ping working end-to-end, then hardware, then polish)

**Q26**: What documentation should be created?
**A**: Option 1 + 2 - Code comments + README updates (docstrings in code + README with config examples)

**Q27**: What should default configuration values be (ping)?
**A**: Reasonable defaults (1s interval, 2s timeout, 100ms/500ms thresholds, 5%/20% packet loss, etc.)

**Q28**: What should default configuration values be (hardware)?
**A**: Reasonable defaults (15min scan interval, 10s SSH timeout, 5 concurrent connections, etc.)

**Q29**: How should DNS resolution failures be handled?
**A**: Option 2 - Retry DNS with backoff (retry 2-3 times before marking unreachable)

**Q30**: How should SSH host key verification be handled?
**A**: Option 1 - Strict verification (only accept known hosts from ~/.ssh/known_hosts)

**Q31**: If some hardware detection succeeds but others fail, how should it be handled?
**A**: Option 1 - Show partial data (display what succeeded, show N/A for failed components)

**Q32**: Should the hardware plugin support SSH agent?
**A**: Option 2 - SSH agent preferred with fallback (try agent first, fall back to key files)

**Q33**: Should hosts be automatically disabled after consecutive failures?
**A**: Option 2 - Auto-disable after N failures (stop checking after N consecutive failures, require manual re-enable)

**Q34**: What visual style should be used for the new panes?
**A**: Option 1 - Match existing panes (use same styling as CPU/Memory/etc. for consistency)

**Q35**: How should the new panes adapt to different display modes?
**A**: Option 1 - Full support for all modes (MICRO/MINIMIZED/MEDIUM/MAXIMIZED with appropriate detail levels)

**Q36**: Any additional features or requirements?
**A**: Ready to generate specification (no additional features requested)

---

**End of Specification**

This specification is now ready for implementation. Agents should work through phases sequentially, completing all tasks within each subphase before moving to the next. Each task includes clear acceptance criteria and should result in working, tested code that passes `task check`.
