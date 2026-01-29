# uptop Specification (Compact)

## Summary
**uptop**: Python CLI+TUI system monitor with btop-like functionality, plugin architecture, multiple output formats.

**Differentiators**: Dual Mode (TUI/CLI) | Plugin Architecture | JSON/Markdown/Prometheus output | Python 3.11+, Textual, Pydantic, psutil

## MVP Scope
**Includes**: Plugin system, Core panes (CPU/Memory/Processes/Network/Disk), TUI with keyboard nav, CLI JSON output, YAML config, process kill
**Excludes**: GPU/Sensors panes, advanced process features, Markdown/Prometheus formatters, query syntax, streaming modes, custom themes, example plugins, --ai-help

**Success**: TUI shows real-time data, can kill process, `uptop --json --once` works, plugin system functional, ≥75% coverage

## Tech Stack
| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| TUI | textual[dev] ≥0.40 |
| CLI | typer[all] ≥0.9 |
| Data | psutil, Pydantic v2 |
| Config | PyYAML |
| Testing | pytest + cov + mock + snapshot + asyncio |
| Quality | ruff, black, isort, mypy |
| Tasks | Taskfile |

**Platforms**: Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+), macOS 12+. No Windows.

## Architecture

```
UI Layer:     TUI (Textual)  |  CLI (Typer)
                    ↓
Plugin Layer: Discovery → Registry → Lifecycle
                    ↓
Plugin API:   PanePlugin | CollectorPlugin | FormatterPlugin | ActionPlugin
                    ↓
Internal:     CPU | Memory | Process | Network | Disk | [GPU] | [Sensors]
                    ↓
Collection:   psutil + vendor libs
```

**Data Flow**: Collector → Pydantic Model → Buffer → (TUI Widget | Formatter → stdout)

**Concurrency**: asyncio throughout. Per-pane async collectors, configurable intervals, graceful degradation on failure. No threading.

### Architecture Principles (Compressed)
- Plugin-first: core features ship as internal plugins to validate APIs early.
- Rendering decoupled from collection (collectors push; UI pulls last snapshot + history buffer).
- Keep a short in-memory history per pane (ring buffer) for graphs/sparklines.

### Async + Thread-Safety Notes (Compressed)
- Plugin APIs are async (`async def collect_data()`); avoid threads.
- Protect shared buffers with asyncio locks; avoid global mutable state (prefer typed Pydantic models).
- Subprocess collectors use `asyncio.create_subprocess_exec()`; long ops should yield (`await asyncio.sleep(0)`).

### Performance Notes (Compressed)
- Per-pane refresh intervals tune load; collectors should fail fast and degrade per-pane (no app-wide crash).

## Development Standards

| Aspect | Requirement |
|--------|-------------|
| Docs | PEP 257 docstrings |
| Types | PEP 484, mypy strict |
| Style | PEP 8 via ruff+black+isort |
| Files | <500 lines preferred, <1000 max |
| Tests | ≥75% coverage overall AND per-module |
| Commits | Conventional Commits |

**Pre-commit**: `task check` → fmt → lint → type → test → coverage

**Commit types**: feat, fix, docs, style, refactor, test, chore, perf, ci, build

### Repo + Workflow Conventions (Compressed)
- Docs live in `docs/` (except `README.md`); completed plans/history in `history/`.
- Secrets live in `secrets/` as `.env` + `.example` templates (never commit real secrets).
- Filenames: Python modules use snake_case; hyphens for non-Python files.
- Taskfile is the canonical entrypoint; default task lists tasks; tasks use robust shell options.
- Git: feature branches; avoid destructive history rewrites unless explicitly approved; squash before merge.

## Core Panes

### CPU
- Metrics: per-core usage, frequency, temperature (if available), load avg (1/5/15)
- Display: per-core bars; optional sparklines (uses history buffer)
- Source: `psutil.cpu_percent(percpu=True)`, `cpu_freq()`, `sensors_temperatures()`

### Memory
- RAM: total/used/free/available/cached/buffers; show percent used
- macOS: best-effort breakdown (wired/active/inactive) when available
- Swap: total/used/free
- Display: bars/progress + optional sparklines (uses history buffer)
- Source: `psutil.virtual_memory()`, `swap_memory()`

### Processes
- Columns: PID, User, CPU%, MEM%, VSZ, RSS, State, Runtime, Command
- MVP actions: sort, filter, kill (SIGTERM/SIGKILL), tree view
- Post-MVP: configurable columns/order, preset filters, detail view (open files/sockets/threads/env), renice
- Source: `psutil.process_iter()` (plus per-process detail APIs when enabled)

### Network
- Per-interface: bytes/packets sent/recv, errors, drops, bandwidth rates
- Connections: TCP/UDP with addr:port, state, PID
- Display: bandwidth graphs from history buffer; active connections table
- Post-MVP: per-process network usage where feasible (may require elevated permissions)
- Source: `psutil.net_io_counters(pernic=True)`, `net_connections()`

### Disk
- Filesystem: used/free/total per mount, percentage
- I/O: read/write bytes/sec, IOPS (and queue depth if available) per disk
- Display: usage bars + I/O graphs from history buffer
- Post-MVP: per-process I/O where supported/available
- Source: `psutil.disk_usage()`, `disk_io_counters()`

### GPU (post-MVP)
- NVIDIA (pynvml): utilization, memory, temp, power, fan; per-process GPU memory
- AMD (pyamdgpuinfo/rocm-smi): utilization, VRAM, temp, clocks
- Intel (intel_gpu_top): utilization, freq/mem (best-effort)
- Apple: model via `system_profiler`; memory pressure; `powermetrics` (sudo) for limited stats
- Limitation: Apple Silicon detailed GPU utilization is not generally available; show best-effort + clear “not available”.

### Sensors (post-MVP)
- Collect: temps/fans/voltages/battery when available (`psutil.sensors_*()`)
- Display: group by sensor type; alerts: warn >80°C, critical >90°C (configurable post-MVP)

## Metric Types

```python
class MetricType(str, Enum):
    COUNTER = "counter"   # Monotonically increasing
    GAUGE = "gauge"       # Can go up/down
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
```

| Type | Behavior | Examples | Aggregation |
|------|----------|----------|-------------|
| Counter | Only increases | bytes_sent, request_count | sum, rate |
| Gauge | Up/down | cpu%, memory, temp | avg/min/max/last |

**Usage**:
```python
from uptop.models import MetricData, counter_field, gauge_field

class NetworkData(MetricData):
    bytes_sent: int = counter_field("Total bytes", ge=0)
    bandwidth: float = gauge_field("Current rate", ge=0.0)
```

**Introspection**: `get_metric_type(Model, "field")` → `MetricType.COUNTER`

## Plugin API

### Pane Plugin
```python
class MyPane(PanePlugin):
    name = "my_pane"
    display_name = "My Pane"
    default_refresh_interval = 2.0

    async def collect_data(self) -> MyData: ...
    def render_tui(self, data: MyData) -> Widget: ...
    def get_schema(self) -> type[BaseModel]: ...
    def get_ai_help_docs(self) -> str: ...  # Optional
```

### Other Plugin Types
- **CollectorPlugin**: Contribute data to existing panes
- **FormatterPlugin**: Custom output formats (--xml, etc.)
- **ActionPlugin**: Process actions with keyboard shortcuts

### Discovery
1. Entry points: `uptop.panes`, `uptop.collectors`, `uptop.formatters`, `uptop.actions`
2. Directory: `~/.uptop/plugins/*.py`

### Versioning
- Plugin declares `api_version = "1.0"`
- Major version = breaking, Minor = additive only
- `uptop --check-plugins` validates compatibility

### Security + Deprecation (Compressed)
- **Trust model**: plugins are trusted code (no sandbox). Installing a plugin == trusting it.
- Actions that modify system state should require confirmation.
- Deprecations remain functional for at least 2 minor versions; log warnings on deprecated API use.

## CLI Modes

```bash
uptop                    # TUI (default if TTY)
uptop --json --once      # Single JSON snapshot
uptop --json --stream    # Continuous JSON output
uptop --markdown --once  # Markdown tables
uptop --prometheus       # Prometheus metrics
```

**Query** (post-MVP): `uptop --json -q "cpu.cores[0].usage"` (JMESPath)

**Aggregation** (post-MVP): `--aggregate avg --duration 60`

**AI help** (post-MVP): `uptop --ai-help` outputs LLM-digestible markdown (CLI ref + config + plugin API + examples). No LLM integration required; user pipes the output to an LLM. Plugins may contribute via `get_ai_help_docs()`.

### CLI Semantics (Compressed)
- Mode inference: `uptop` (TUI if TTY), `uptop tui`, `uptop cli --json`, or `uptop --json` implies CLI.
- Output modes: `--once` (snapshot then exit; default for non-TTY), `--stream` (NDJSON/JSONL per interval), `--continuous` (ANSI in-place redraw).
- Common flags: `--config PATH`, `--interval`, `--panes`; TUI flags: `--theme`, `--layout`, `--no-mouse` (post-MVP as needed).
- `--verbose` / `--log-file` (post-MVP): include plugin load results, collection errors, per-pane collection latency.

## Configuration

Location: `~/.config/uptop/config.yaml`

```yaml
default_mode: tui
interval: 1.0

tui:
  theme: dark  # dark|light|solarized|nord|gruvbox
  mouse_enabled: true
  panes:
    cpu: {enabled: true, refresh_interval: 1.0}
    memory: {enabled: true, refresh_interval: 2.0}
    processes: {enabled: true, default_sort: cpu_percent}
  keybindings: {quit: q, help: "?", filter: /, kill_process: k}

cli:
  default_format: json
  pretty_print: true

plugins:
  directory: ~/.uptop/plugins
  auto_load: true
```

### Config Schema (Compressed)
Config supports (at minimum):
- `tui.panes.<name>`: `enabled`, `refresh_interval`, and (post-MVP) layout metadata like `position`/`size`
- `tui.layouts`: named layouts + a `default` layout selector
- `tui.keybindings`: configurable shortcuts (global + process pane)
- `cli`: `default_format` (`json|markdown|prometheus`), output mode (`once|stream|continuous`), `pretty_print`
- `display.units`: memory (`binary|decimal`), network units, temperature (`celsius|fahrenheit`), `decimal_places`
- `plugins`: `enabled_plugins`, plus `plugin_config.<plugin_name>` (plugin-specific settings)
- `process_filters`: named presets (e.g. high_cpu/high_mem/my_user)
- `logging`: enable/level/file (debugging)
- Env var expansion in config values (`${VAR}`), plus `UPTOP_CONFIG_PATH` override (post-MVP if needed)

## Customization (Compressed)
- Themes: built-ins `dark|light|solarized|nord|gruvbox`; post-MVP custom theme via Textual CSS path.
- Layout: presets + named layouts; post-MVP `:save-layout <name>`; resize/rearrange (mouse/keyboard) when feasible.
- Units: memory binary/decimal; network bps vs Bps (auto-scale); temperature C/F; configurable precision.

## Error Handling & Edge Cases
- Pane failure should only affect that pane: show error state + keep rest of UI updating.
- Retry collectors with backoff; show stale-data indicator if a refresh fails.
- Permission errors: show actionable messages; disable privileged features gracefully.
- Missing resources: hide/disable panes or show “not available” (no GPU, no interfaces, missing optional deps).
- Verbose/debug logging should include plugin load results, collection errors, and per-pane collection latency.

## Accessibility (Compressed)
- Keyboard-first: all core actions available via keyboard; clear focus indicators.
- Avoid color-only status; use symbols/text as fallback.
- High contrast theme option (post-MVP). Textual screen reader support is limited; CLI output is the accessibility fallback.
- Reduced motion mode (post-MVP) to disable animations/blinking.

## Keyboard Shortcuts

| Key | Action | Scope |
|-----|--------|-------|
| q | Quit | Global |
| ? | Help | Global |
| r | Refresh | Global |
| Tab | Next pane | Global |
| / | Filter | Process |
| s | Sort | Process |
| k | Kill | Process |
| t | Tree view | Process |

## Implementation Phases

### Phase 0: Setup ✓ COMPLETE
Repository, pyproject.toml, Taskfile, CI/CD, docs structure, code quality tools.

### Phase 1: Core Architecture ✓ COMPLETE
**1.1** Plugin API Design | **1.2** Plugin Loading | **1.3** Configuration | **1.4** Data Collection

### Phase 2: Core Panes ✓ COMPLETE
**2.1** CPU | **2.2** Memory | **2.3** Processes | **2.4** Network | **2.5** Disk
*(2.6 GPU, 2.7 Sensors = post-MVP)*

---

### Phase 3: TUI

#### 3.1 App Shell
- **3.1.1** Create `src/uptop/tui/app.py`: UptopApp(App) class, compose() method, basic screen
- **3.1.2** Create `src/uptop/tui/__init__.py`: exports
- **3.1.3** Wire app launch from CLI (`uptop` command → TUI mode)
- **3.1.4** Tests for app instantiation and basic lifecycle

#### 3.2 Pane Container Widget
- **3.2.1** Create `src/uptop/tui/widgets/pane_container.py`: PaneContainer(Widget) with title bar, content area, border
- **3.2.2** Add refresh indicator, error state display
- **3.2.3** Tests for PaneContainer rendering

#### 3.3 Grid Layout
- **3.3.1** Create `src/uptop/tui/layouts/grid.py`: GridLayout class managing pane arrangement
- **3.3.2** Default layout: CPU+Memory top row, Processes middle, Network+Disk bottom
- **3.3.3** Implement pane focus cycling (Tab/Shift+Tab)
- **3.3.4** Tests for layout and focus management

#### 3.4 Pane Integration
- **3.4.1** Create `src/uptop/tui/panes/cpu_widget.py`: CPUWidget rendering CPUData with progress bars
- **3.4.2** Create `src/uptop/tui/panes/memory_widget.py`: MemoryWidget with RAM/Swap bars
- **3.4.3** Create `src/uptop/tui/panes/process_widget.py`: ProcessWidget with DataTable
- **3.4.4** Create `src/uptop/tui/panes/network_widget.py`: NetworkWidget with interface list
- **3.4.5** Create `src/uptop/tui/panes/disk_widget.py`: DiskWidget with mount/IO display
- **3.4.6** Tests for each pane widget

#### 3.5 Data Refresh Loop
- **3.5.1** Implement async refresh loop in UptopApp using set_interval()
- **3.5.2** Per-pane refresh intervals from config
- **3.5.3** Error handling: show stale data indicator on collection failure
- **3.5.4** Tests for refresh behavior

#### 3.6 Global Keybindings
- **3.6.1** Implement quit (q), help (?), refresh (r) bindings
- **3.6.2** Create help modal/overlay showing all keybindings
- **3.6.3** Tests for global key handling

#### 3.7 Process Pane Keybindings
- **3.7.1** Implement sort toggle (s) with column cycle
- **3.7.2** Implement filter input (/) with text input modal
- **3.7.3** Implement kill process (k) with confirmation dialog
- **3.7.4** Implement tree view toggle (t)
- **3.7.5** Tests for process-specific bindings

#### 3.8 Mouse Support
- **3.8.1** Enable mouse in app, handle pane clicks for focus
- **3.8.2** Process list row selection via mouse
- **3.8.3** Scrolling in process list
- **3.8.4** Tests for mouse interactions

#### 3.9 Theming
- **3.9.1** Create `src/uptop/tui/themes/` with base theme structure
- **3.9.2** Implement dark theme (default)
- **3.9.3** Implement light theme
- **3.9.4** Theme loading from config
- **3.9.5** Tests for theme application

#### 3.10 History & Sparklines (MVP-optional)
- **3.10.1** Add sparkline widget for CPU/Memory history
- **3.10.2** Wire ring buffer data to sparklines
- **3.10.3** Tests for sparkline rendering

---

### Phase 4: CLI & Formatters

#### 4.1 JSON Formatter
- **4.1.1** Create `src/uptop/formatters/json_formatter.py`: JsonFormatter(FormatterPlugin)
- **4.1.2** Implement format() method using Pydantic model_dump_json()
- **4.1.3** Support pretty_print config option
- **4.1.4** Tests for JSON output correctness

#### 4.2 CLI --once Mode
- **4.2.1** Implement --once flag: single collection cycle, output, exit
- **4.2.2** Collect from all enabled panes
- **4.2.3** Output via selected formatter (default: JSON)
- **4.2.4** Tests for --once behavior

#### 4.3 CLI --stream Mode (post-MVP)
- **4.3.1** Implement --stream flag: continuous output with interval
- **4.3.2** NDJSON format (newline-delimited)
- **4.3.3** Graceful SIGINT handling
- **4.3.4** Tests for streaming output

#### 4.4 Prometheus Formatter
- **4.4.1** Create `src/uptop/formatters/prometheus.py`: PrometheusFormatter
- **4.4.2** Use MetricType introspection for TYPE comments
- **4.4.3** Generate proper metric names with labels
- **4.4.4** Tests for Prometheus format compliance

#### 4.5 Markdown Formatter (post-MVP)
- **4.5.1** Create `src/uptop/formatters/markdown.py`: MarkdownFormatter
- **4.5.2** Render tables for each pane's data
- **4.5.3** Tests for Markdown output

#### 4.6 Pane Selection
- **4.6.1** Implement --panes flag to select specific panes
- **4.6.2** Validate pane names against registry
- **4.6.3** Tests for pane filtering

#### 4.7 Help System
- **4.7.1** Implement --help with full command documentation
- **4.7.2** Implement --version
- **4.7.3** Implement --check-plugins for plugin validation
- **4.7.4** Tests for help output

---

### Phase 5: Example Plugins (post-MVP, PARALLEL)

#### 5.1 Hello World Plugin
- **5.1.1** Create `examples/plugins/hello_world.py`: minimal PanePlugin
- **5.1.2** Document as plugin development tutorial

#### 5.2 Docker Plugin
- **5.2.1** Create `examples/plugins/docker_pane.py`: container list pane
- **5.2.2** Use docker SDK or CLI
- **5.2.3** Tests with mocked docker

#### 5.3 Weather Plugin
- **5.3.1** Create `examples/plugins/weather.py`: external API example
- **5.3.2** Demonstrate async HTTP in collector

#### 5.4 Log Monitor Plugin
- **5.4.1** Create `examples/plugins/log_monitor.py`: tail log files
- **5.4.2** Demonstrate file watching pattern

---

### Phase 6: Testing

#### 6.1 Unit Test Coverage
- **6.1.1** Ensure all modules have ≥75% coverage
- **6.1.2** Add missing edge case tests
- **6.1.3** Mock external dependencies (psutil, filesystem)

#### 6.2 Integration Tests
- **6.2.1** Create `tests/integration/test_cli.py`: end-to-end CLI tests
- **6.2.2** Create `tests/integration/test_tui.py`: TUI app tests using pilot
- **6.2.3** Test plugin discovery and loading

#### 6.3 Snapshot Tests
- **6.3.1** Add snapshot tests for JSON output format
- **6.3.2** Add snapshot tests for Prometheus output
- **6.3.3** Add snapshot tests for TUI renders (if feasible)

#### 6.4 Performance Tests
- **6.4.1** Benchmark collection latency (<100ms target)
- **6.4.2** Measure memory usage (<100MB target)
- **6.4.3** CPU usage during idle (<5% target)

---

### Phase 7: Documentation

#### 7.1 README
- **7.1.1** Installation instructions (pip, brew)
- **7.1.2** Quick start guide
- **7.1.3** Feature overview with screenshots

#### 7.2 User Guide
- **7.2.1** CLI reference with all flags
- **7.2.2** TUI navigation guide
- **7.2.3** Configuration reference

#### 7.3 Plugin Development Guide
- **7.3.1** Plugin API reference
- **7.3.2** Step-by-step tutorial (Hello World)
- **7.3.3** Best practices and patterns

#### 7.4 Man Pages
- **7.4.1** Generate uptop(1) man page
- **7.4.2** Include in package

---

### Phase 8: Packaging

#### 8.1 PyPI
- **8.1.1** Finalize pyproject.toml metadata
- **8.1.2** Build and test wheel
- **8.1.3** Publish to PyPI

#### 8.2 Homebrew (post-MVP)
- **8.2.1** Create Homebrew formula
- **8.2.2** Submit to homebrew-core or tap

#### 8.3 System Packages (post-MVP)
- **8.3.1** Create APT package spec
- **8.3.2** Create RPM spec

---

### Phase 9: Polish

#### 9.1 Performance
- **9.1.1** Profile and optimize hot paths
- **9.1.2** Reduce memory allocations in collectors
- **9.1.3** Optimize TUI render cycles

#### 9.2 Error Handling
- **9.2.1** Graceful degradation for missing permissions
- **9.2.2** Clear error messages for config issues
- **9.2.3** Recovery from transient failures

#### 9.3 UX Polish
- **9.3.1** Improve startup time
- **9.3.2** Smooth transitions and animations
- **9.3.3** Accessibility review

#### 9.4 Security
- **9.4.1** Review process kill permissions
- **9.4.2** Verify + document plugin trust model (no sandbox; warn users)
- **9.4.3** Audit dependencies

## Dependencies

**Core**: psutil≥5.9, textual[dev]≥0.40, typer[all]≥0.9, pydantic≥2.0, PyYAML≥6.0

**Optional**: pynvml, pyamdgpuinfo (GPU), jmespath (query), docker (Docker plugin), requests (Weather plugin)

**Dev**: pytest, pytest-cov, pytest-mock, pytest-asyncio, pytest-snapshot, black, isort, ruff, mypy

**System** (conditional):
- Linux: `/proc` for richer process/network info; optional tools `nvidia-smi`, `rocm-smi`, `intel_gpu_top`.
- macOS: `system_profiler`, `sysctl`; `powermetrics` (sudo) for limited GPU stats.

**Docs** (post-MVP): mkdocs-material, mkdocstrings[python], click-man.

## Success Criteria (Expanded)
- MVP: TUI runs and shows CPU/Memory/Processes/Network/Disk; can kill a process; `--json --once` works.
- Plugin discovery works (entry points + directory) and failures are isolated.
- Config loads + validates; sensible defaults when missing.

## Testing Strategy (Compressed)
- Unit tests: models, collectors, plugin registry/loader, formatters.
- Integration tests: CLI end-to-end; TUI smoke tests; plugin discovery.
- Snapshot tests: formatter output (JSON/Prometheus), and TUI render snapshots if feasible.
- Perf tests: `pytest-benchmark`, `cProfile`, `memory_profiler` (targets below).
- Cross-platform validation: Linux + macOS for core panes.

## Testing Targets

|| Type | Target |
||------|--------|
|| Coverage | ≥75% overall AND per-module |
|| CPU usage | <5% |
|| Memory | <100MB |
|| Collection latency | <100ms per pane |
|| Startup | <2s |

## Prometheus Metrics (Reference)

| Metric | Type | Labels |
|--------|------|--------|
| uptop_cpu_usage_percent | gauge | core |
| uptop_cpu_freq_mhz | gauge | core |
| uptop_memory_bytes | gauge | type |
| uptop_network_bytes_total | counter | interface, direction |
| uptop_disk_usage_bytes | gauge | mountpoint, type |
| uptop_disk_io_bytes_total | counter | disk, direction |
| uptop_process_count | gauge | state |

## Entry Points Schema

```python
entry_points={
    'uptop.panes': ['name = pkg.mod:PaneClass'],
    'uptop.collectors': ['name = pkg.mod:CollectorClass'],
    'uptop.formatters': ['name = pkg.mod:FormatterClass'],
    'uptop.actions': ['name = pkg.mod:ActionClass'],
}
```

## Open Questions (2026-01-04)
- Textual drag-to-resize feasibility; fallback: keyboard resize.
- Textual snapshot testing support; fallback: pilot-based smoke tests or screenshot comparisons.
- Weather plugin API: wttr.in (no key) vs OpenWeatherMap (key).
- Packaging priority: Homebrew → APT → RPM.

## Timeline (Rough)
- With parallel agents, overall delivery is ~8–12 weeks (varies by scope and post-MVP features).

## License & Contribution
- License: MIT. Contributions via PRs; encourage community plugins.

## Revision History (Compressed)
- v1.4 (2026-01-04): Restored key context from `SPECIFICATION.md.old` while keeping compact format.
- v1.3 (2026-01-03): Converted spec to compact form; expanded phases into finer sub-phases.

---
**Version**: 1.4 | **Updated**: 2026-01-04

**For Agents**:
- Each numbered task (e.g., 3.1.1, 3.1.2) is a single agent-sized unit of work
- Complete all sub-tasks within a sub-phase before marking it done
- Sub-phases within the same phase can often run in parallel (e.g., 3.4.1-3.4.5)
- Always run `task check` before commits
- Use feature branches per sub-phase (e.g., `feat/3.1-app-shell`)
