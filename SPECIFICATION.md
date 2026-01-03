# uptop - Universal Performance & Telemetry Output

## Executive Summary

**uptop** is a modern CLI+TUI system monitoring tool written in Python that provides btop-like functionality with extensibility and multiple output formats. It combines an interactive terminal UI with powerful command-line data export capabilities and a plugin architecture for community extensions.

### Key Differentiators
- **Dual Mode**: Interactive TUI and scriptable CLI with structured output
- **Plugin Architecture**: Extensible via Python plugins (entry points + local directory)
- **Multiple Formats**: JSON, Markdown, and Prometheus output for integration
- **Modern Stack**: Python 3.10+, Textual TUI, Pydantic data models, psutil

---

## Technical Decisions

### Core Technology Stack
- **Language**: Python 3.11+ (for improved type hints, match statements, modern features)
- **TUI Framework**: textual[dev] (modern, powerful, CSS-like styling, async-native)
- **CLI Framework**: typer[all] (type-hint based CLI, built on Click)
- **Data Collection**: psutil (cross-platform, comprehensive)
- **Data Models**: Pydantic v2 (validation, serialization, type safety)
- **Configuration**: YAML via PyYAML or ruamel.yaml
- **Testing**: pytest + pytest-cov + pytest-mock + pytest-snapshot
- **Code Quality**: ruff (linting) + black (formatting) + isort (imports) + mypy (type checking)
- **Task Runner**: Taskfile (task automation and workflow orchestration)

### Platform Support
- **Primary**: Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+)
- **Secondary**: macOS 12+ (Monterey and later)
- **Not Supported**: Windows (future consideration)

### Architecture Philosophy
**Plugin-First Architecture**: Minimal core with internal plugins for all features. This approach:
- Validates plugin system from day one
- Forces clean abstractions and APIs
- Makes core features serve as plugin examples
- Enables easy feature addition/removal

### Development Standards

**Code Quality Requirements**:
- **Documentation**: PEP 257 docstrings for all public APIs
- **Type Hints**: PEP 484 type hints for all functions and methods, mypy strict mode
- **Style**: PEP 8 compliance via ruff + black + isort
- **File Size**: Files SHOULD be < 500 lines, MUST be < 1000 lines
- **Testing**: ≥75% code coverage overall AND per-module
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) format

**Conventional Commit Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code restructuring (no feature/bug change)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `build`: Build system changes

**Testing Requirements**:
- All code must have tests (pytest)
- Coverage: ≥75% overall + ≥75% per-module
- Use pytest-cov for coverage reporting
- Use pytest-mock for mocking
- Exclude `__main__` and entry points from coverage
- Integration tests for critical paths
- Snapshot tests for formatters

**Pre-Commit Workflow**:
```bash
task check  # ALWAYS run before committing
```

This runs:
1. `task fmt` - Format code (black, isort)
2. `task lint` - Lint code (ruff)
3. `task type` - Type check (mypy)
4. `task test` - Run tests
5. `task test:coverage` - Verify coverage ≥75%

**Project Organization**:
- **Documentation**: All `*.md` files in `docs/`, never in root (except README.md)
- **Filenames**: Use hyphens not underscores (`data-collector.py` not `data_collector.py` for files, snake_case for Python modules)
- **Secrets**: ALL secrets in `secrets/` directory as `.env` files with `.example` templates
- **History**: Completed plans and historical docs in `history/`

**Taskfile Structure**:
- All repeatable tasks in `Taskfile.yml`
- Task targets: `build`, `test`, `test:coverage`, `fmt`, `lint`, `type`, `quality`, `check`, `clean`
- Shell options: `set: [errexit, nounset, pipefail]` for robustness
- Add `desc` for all user-facing tasks
- `task --list` shows all available tasks

**Git Workflow**:
- Never use `git reset --hard` or force-push without explicit permission
- Prefer safe alternatives (`git revert`, new commits, temporary branches)
- Feature branches for all development
- Squash commits before merging to main

---

## System Architecture

### Component Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│  ┌──────────────────────┐    ┌──────────────────────────┐  │
│  │   TUI (Textual)      │    │   CLI (Click/Typer)      │  │
│  │  - Interactive mode   │    │  - Streaming output      │  │
│  │  - Keyboard/mouse     │    │  - Single snapshots      │  │
│  │  - Theming           │    │  - Format selection      │  │
│  └──────────────────────┘    └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Plugin Management Layer                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Plugin Discovery & Loading                           │  │
│  │  - Entry points (pip packages)                        │  │
│  │  - Directory scanning (~/.uptop/plugins/)             │  │
│  │  - Dependency injection                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Core Plugin API                         │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐ │
│  │  Panes     │ │Collectors│ │ Formatters│ │  Actions   │ │
│  │  Abstract  │ │ Abstract │ │  Abstract │ │  Abstract  │ │
│  └────────────┘ └──────────┘ └───────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Internal Plugins (Bundled)                  │
│  ┌──────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐ │
│  │ CPU  │ │ Memory │ │ Process  │ │Network │ │  Disk   │ │
│  │ Pane │ │  Pane  │ │   Pane   │ │  Pane  │ │  Pane   │ │
│  └──────┘ └────────┘ └──────────┘ └────────┘ └─────────┘ │
│  ┌──────┐ ┌─────────────────────────────────────────────┐ │
│  │ GPU  │ │         Sensors Pane                        │ │
│  │ Pane │ │  (CPU temp, fan speeds, voltages)           │ │
│  └──────┘ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Data Collection Layer                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  psutil + Specialized Libraries                       │  │
│  │  - CPU: psutil, py-cpuinfo                           │  │
│  │  - GPU: pynvml (NVIDIA), pyamdgpuinfo (AMD),         │  │
│  │         intel-gpu-tools, Apple Metal via subprocess  │  │
│  │  - Network: psutil + /proc parsing for per-process   │  │
│  │  - Sensors: psutil.sensors_* APIs                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Collection Loop (per-pane configurable interval)
    ↓
Collector Plugin (gathers raw metrics)
    ↓
Pydantic Model (validation & normalization)
    ↓
In-Memory Buffer (limited history for graphs)
    ↓
┌──────────────────────────────┬─────────────────────────────┐
│   TUI Path                   │      CLI Path               │
├──────────────────────────────┼─────────────────────────────┤
│ Pane Plugin (rendering)      │ Formatter Plugin (JSON/etc) │
│     ↓                        │     ↓                       │
│ Textual Widgets              │ stdout (streaming/snapshot) │
│     ↓                        │                             │
│ Terminal Display             │                             │
└──────────────────────────────┴─────────────────────────────┘
```

---

## Core Features Specification

### 1. Core Monitoring Panes (Internal Plugins)

#### 1.1 CPU Pane
- **Per-core usage**: Individual core utilization (0-100%)
- **Frequency**: Current/min/max frequencies per core
- **Load averages**: 1, 5, 15 minute averages
- **Temperature**: Per-core temps if available via psutil
- **Visualization**: Horizontal bar graphs per core, historical sparklines
- **Data source**: `psutil.cpu_percent(percpu=True)`, `psutil.cpu_freq()`, `psutil.sensors_temperatures()`

#### 1.2 Memory & Swap Pane
- **RAM usage**: Total, used, free, available, cached, buffers
- **Swap usage**: Total, used, free
- **Percentages**: Visual indicators for used/total ratios
- **Breakdown**: Memory type breakdown (wired, active, inactive on macOS)
- **Data source**: `psutil.virtual_memory()`, `psutil.swap_memory()`

#### 1.3 Process Pane
**Display**:
- Columns: PID, User, CPU%, MEM%, VSZ, RSS, State, Runtime, Command
- Tree view mode (parent-child hierarchy)
- Configurable column visibility and order

**Interactions**:
- Sort by any column (ascending/descending)
- Smart filter: type-ahead search across multiple fields
- Preset filters: "my processes", "high CPU (>50%)", "high mem (>100MB)", user-defined
- Process detail view: show open files, network sockets, threads, environment

**Actions** (keyboard shortcuts):
- Kill (SIGTERM/SIGKILL with confirmation)
- Change priority (renice)
- Jump to process detail
- Filter by user

**Data source**: `psutil.process_iter()`, `Process.open_files()`, `Process.connections()`

#### 1.4 Network Pane
- **Interface statistics**: Bytes sent/received, packets, errors, drops per interface
- **Bandwidth graphs**: Historical upload/download rates (last N minutes in memory)
- **Active connections**: TCP/UDP connections with local/remote addr:port, state, PID
- **Per-process network**: Network usage per process (requires elevated permissions on some systems)
- **Data source**: `psutil.net_io_counters(pernic=True)`, `psutil.net_connections()`

#### 1.5 Disk Pane
- **Filesystem usage**: Used/free/total per mount point, usage percentage
- **Disk I/O**: Read/write bytes/sec, IOPS, queue depth per disk
- **Per-process I/O**: Disk read/write rates per process if available
- **Visualization**: Usage bars, I/O rate graphs
- **Data source**: `psutil.disk_usage()`, `psutil.disk_io_counters()`, `Process.io_counters()`

#### 1.6 GPU Pane (Multi-Vendor)
**NVIDIA** (via pynvml):
- GPU utilization, memory usage, temperature, power draw, fan speed
- Per-process GPU memory usage

**AMD** (via pyamdgpuinfo or ROCm tools):
- GPU utilization, VRAM usage, temperature, clock speeds

**Intel** (via intel_gpu_top subprocess):
- GPU usage, memory, frequency

**Apple** (via Metal API or subprocess to system_profiler):
- GPU activity, memory pressure

**Display**: Show all detected GPUs, gracefully handle missing vendors

#### 1.7 Sensors Pane
- **All available sensors**: CPU temp, chassis fans, voltage rails, GPU temp, etc.
- **Auto-discovery**: Use `psutil.sensors_temperatures()`, `psutil.sensors_fans()`
- **Grouping**: Group by sensor type (temperatures, fans, voltages)
- **Alerts**: Visual indicators for high temps (>80°C warning, >90°C critical)

### 2. CLI Mode Features

#### 2.1 Output Modes
**Flags**:
- `--stream`: Continuous output, new JSON object per interval
- `--once`: Single snapshot then exit (default for non-TTY)
- `--continuous`: Update in-place using ANSI codes (like watch)

**Examples**:
```bash
uptop --json --stream --interval 2  # JSON every 2 seconds
uptop --json --once                 # Single JSON snapshot
uptop --markdown --stream           # Markdown tables continuously
```

#### 2.2 Output Formats

**JSON** (`--json`):
```json
{
  "timestamp": "2026-01-03T10:30:45Z",
  "cpu": {
    "cores": [
      {"id": 0, "usage": 45.2, "freq_mhz": 2800, "temp_c": 65.0},
      ...
    ],
    "load_avg": [1.2, 1.5, 1.8]
  },
  "memory": {
    "total_bytes": 17179869184,
    "used_bytes": 12884901888,
    "percent": 75.0
  },
  ...
}
```

**Markdown** (`--markdown`):
Tables for each pane with GitHub-flavored markdown

**Prometheus** (`--prometheus`):
```
# HELP uptop_cpu_usage_percent CPU usage percentage per core
# TYPE uptop_cpu_usage_percent gauge
uptop_cpu_usage_percent{core="0"} 45.2
uptop_cpu_usage_percent{core="1"} 32.1
...
```

#### 2.3 Query & Aggregation

**Query Syntax** (using JMESPath):
```bash
uptop --json --once -q "cpu.cores[0].usage"  # Extract specific value
uptop --json -q "processes[?cpu_percent > \`50\`]"  # Filter processes
```

**Aggregations**:
```bash
uptop --json --interval 1 --duration 60 --aggregate avg  # Average over 60s
uptop --json --interval 1 --duration 60 --aggregate max  # Peak values
```

#### 2.4 Help System
- **Standard help**: `uptop --help` with comprehensive usage
- **AI help**: `uptop --ai-help` integrates dashdash pattern (https://github.com/visionik/dashdash)
  - Uses LLM to answer natural language questions about uptop usage
  - Examples: `uptop --ai-help "how do I monitor docker containers"`

### 3. Plugin System

#### 3.1 Plugin Discovery

**Entry Points** (installed packages):
```python
# In plugin package setup.py or pyproject.toml
entry_points={
    'uptop.panes': [
        'docker = uptop_plugin_docker:DockerPane',
    ],
    'uptop.collectors': [...],
    'uptop.formatters': [...],
    'uptop.actions': [...]
}
```

**Directory-based** (`~/.uptop/plugins/`):
- Drop Python files directly into plugins directory
- Auto-discovered on startup
- Good for quick custom plugins

#### 3.2 Plugin API Abstractions

**Pane Plugin**:
```python
from uptop.plugin_api import PanePlugin, PaneData
from pydantic import BaseModel

class MyData(BaseModel):
    value: float
    label: str

class MyPane(PanePlugin):
    name = "my_pane"
    display_name = "My Custom Pane"
    default_refresh_interval = 2.0  # seconds

    async def collect_data(self) -> MyData:
        """Gather data - called at refresh_interval"""
        return MyData(value=42.0, label="Answer")

    def render_tui(self, data: MyData) -> Widget:
        """Return Textual widget for TUI display"""
        return Label(f"{data.label}: {data.value}")

    def get_schema(self) -> type[BaseModel]:
        """Return Pydantic model for data validation"""
        return MyData
```

**Collector Plugin** (contribute data to existing panes):
```python
from uptop.plugin_api import CollectorPlugin

class CustomProcessInfo(CollectorPlugin):
    target_pane = "process"  # Contribute to process pane

    def collect(self, process: psutil.Process) -> dict:
        """Return additional fields for process"""
        return {"custom_metric": calculate_metric(process)}
```

**Formatter Plugin**:
```python
from uptop.plugin_api import FormatterPlugin

class XMLFormatter(FormatterPlugin):
    format_name = "xml"
    cli_flag = "--xml"

    def format(self, data: dict) -> str:
        """Convert Pydantic models to XML"""
        return dicttoxml(data)
```

**Action Plugin**:
```python
from uptop.plugin_api import ActionPlugin

class RestartServiceAction(ActionPlugin):
    name = "restart_service"
    keyboard_shortcut = "r"
    requires_confirmation = True

    def can_execute(self, context) -> bool:
        """Check if action is available in current context"""
        return context.selected_process is not None

    async def execute(self, context):
        """Perform action"""
        subprocess.run(["systemctl", "restart", context.selected_process.name()])
```

#### 3.3 Security Model
- **Trust-based**: No sandboxing or permission system
- **User responsibility**: Installing a plugin = trusting it (like pip install)
- **Confirmation**: Actions that modify system require user confirmation
- **Documentation**: Clear warnings in plugin dev guide about security

#### 3.4 Example Plugins (Shipped with uptop)

**Docker Plugin** (`uptop.plugins.docker`):
- Shows running containers, CPU/mem per container, container states
- Demonstrates external API access (Docker socket)

**Custom Pane Example** (`uptop.plugins.hello`):
- Minimal "Hello World" pane for learning
- Well-commented code as tutorial

**Weather Plugin** (`uptop.plugins.weather`):
- Fetch weather from external API
- Demonstrates HTTP calls, caching, non-system data

**Log Monitor Plugin** (`uptop.plugins.logmon`):
- Tail log files with regex filtering and highlighting
- Demonstrates file I/O and text processing

### 4. Configuration System

#### 4.1 Configuration File (`~/.config/uptop/config.yaml`)

```yaml
# Core settings
default_mode: tui  # tui or cli
interval: 1.0  # Default refresh interval (seconds)

# TUI settings
tui:
  theme: dark  # dark, light, solarized, nord, custom
  mouse_enabled: true

  # Pane configuration
  panes:
    cpu:
      enabled: true
      refresh_interval: 1.0
      position: [0, 0]  # Grid position
      size: [2, 1]      # Grid size (width, height)

    memory:
      enabled: true
      refresh_interval: 2.0
      position: [0, 1]
      size: [1, 1]

    processes:
      enabled: true
      refresh_interval: 2.0
      position: [2, 0]
      size: [2, 2]
      default_sort: cpu_percent
      default_filter: null

    network:
      enabled: true
      refresh_interval: 1.0

    disk:
      enabled: true
      refresh_interval: 5.0

    gpu:
      enabled: auto  # auto-detect
      refresh_interval: 1.0

    sensors:
      enabled: true
      refresh_interval: 3.0

  # Layout presets
  layouts:
    default: standard
    custom_layouts:
      server_focus:  # Custom layout for server monitoring
        - [cpu, memory]
        - [network, disk]
      dev_focus:     # Custom layout for development
        - [cpu, processes]
        - [memory, disk]

  # Keyboard shortcuts (configurable)
  keybindings:
    quit: q
    help: "?"
    filter: /
    kill_process: k
    change_priority: n
    refresh: r
    toggle_tree: t
    next_sort: s

# CLI settings
cli:
  default_format: json  # json, markdown, prometheus
  default_output_mode: once  # once, stream, continuous
  pretty_print: true

# Display preferences
display:
  units:
    memory: binary  # binary (KiB) or decimal (KB)
    network: decimal
    temperature: celsius  # celsius or fahrenheit

  decimal_places: 1
  show_percentages: true

# Plugin settings
plugins:
  directory: ~/.uptop/plugins
  auto_load: true
  enabled_plugins:
    - docker
    - weather

  # Plugin-specific config
  plugin_config:
    docker:
      socket: /var/run/docker.sock
    weather:
      api_key: ${WEATHER_API_KEY}  # Environment variable
      location: "San Francisco, CA"
      cache_duration: 600  # seconds

# Process filters presets
process_filters:
  high_cpu: "cpu_percent > 50"
  high_mem: "memory_mb > 100"
  my_user: "username == '${USER}'"

# Logging (for debugging)
logging:
  enabled: false
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: ~/.uptop/uptop.log
```

#### 4.2 Command-Line Argument Structure (Hybrid)

**Mode is optional and inferred**:
```bash
uptop                    # TUI mode (default if TTY)
uptop tui                # Explicit TUI mode
uptop cli --json         # Explicit CLI mode
uptop --json             # Inferred CLI mode (format flag present)
```

**Common flags**:
```bash
uptop --config /path/to/config.yaml  # Custom config
uptop --interval 2                    # Override default interval
uptop --panes cpu,memory,processes    # Show only specific panes
```

**TUI-specific flags**:
```bash
uptop --theme solarized
uptop --layout server_focus
uptop --no-mouse
```

**CLI-specific flags**:
```bash
uptop --json --stream --interval 1
uptop --markdown --once
uptop --prometheus --stream
uptop -q "cpu.cores[0].usage"           # Query
uptop --aggregate avg --duration 60     # Aggregation
```

### 5. Customization

#### 5.1 Color Themes

**Built-in themes**:
- `dark` (default): Dark background, bright accents
- `light`: Light background, muted colors
- `solarized`: Solarized color palette
- `nord`: Nord color scheme
- `gruvbox`: Gruvbox theme

**Custom themes** (via Textual CSS):
```yaml
tui:
  theme: custom
  custom_theme_path: ~/.config/uptop/themes/my_theme.css
```

#### 5.2 Layout Configuration
- Drag-and-drop pane arrangement (TUI)
- Resize panes with mouse or keyboard
- Save current layout as preset via command (`:save-layout my_layout`)
- Switch layouts with keybinding or command

#### 5.3 Display Units
- Memory: KiB/MiB/GiB vs KB/MB/GB
- Network: bps vs Bps, auto-scaling
- Temperature: Celsius vs Fahrenheit
- Configurable decimal precision

### 6. Error Handling & Edge Cases

#### 6.1 Graceful Degradation
- If a pane fails to collect data, display error in that pane only
- Continue updating other panes
- Retry failed panes with exponential backoff

#### 6.2 Verbose Logging
```bash
uptop --verbose             # Log to stderr
uptop --verbose --log-file /tmp/uptop.log  # Log to file
```

Logs include:
- Plugin loading success/failure
- Data collection errors
- Performance metrics (collection time per pane)

#### 6.3 Permission Handling
- Detect permission errors (e.g., killing other user's processes)
- Show clear error messages with suggestions:
  - "Permission denied. Try running with sudo."
  - "Process network monitoring requires root. Run: sudo uptop"
- Gracefully disable features that need permissions

#### 6.4 Offline/Missing Resources
- No GPU: Hide GPU pane or show "No GPU detected"
- No network interfaces: Show message in network pane
- /proc unavailable (non-Linux): Fall back to psutil only
- Missing optional dependencies: Show installation hint

---

## Implementation Plan

### Phase 0: Project Setup (No dependencies)
**Goal**: Establish project infrastructure before any coding

**Tasks** (can run in parallel):

**0.1 Repository Setup**
- [ ] Create GitHub repository with MIT license
- [ ] Setup .gitignore for Python projects
- [ ] Create initial README.md with project description
- [ ] Setup branch protection rules for main branch

**0.2 Development Environment**
- [ ] Create pyproject.toml with project metadata (see Appendix G)
- [ ] Define Python version requirement (>=3.11)
- [ ] Create Taskfile.yml with core tasks (see Appendix H)
- [ ] Create secrets/ directory with .gitignore and .example templates
- [ ] Create history/ directory for completed plans
- [ ] Create virtual environment instructions in docs/

**0.3 CI/CD Pipeline**
- [ ] Create GitHub Actions workflow for tests (.github/workflows/test.yml)
- [ ] Create GitHub Actions workflow for linting (.github/workflows/lint.yml)
- [ ] Setup matrix testing for Python 3.11, 3.12
- [ ] Setup matrix testing for Ubuntu 22.04, Ubuntu 24.04, macOS 13, macOS 14
- [ ] Workflow runs `task check` for all quality gates

**0.4 Documentation Structure**
- [ ] Create docs/ directory structure
- [ ] Setup mkdocs.yml configuration
- [ ] Create CONTRIBUTING.md template
- [ ] Create issue templates (bug report, feature request)
- [ ] Create PR template

**0.5 Code Quality Tools**
- [ ] Add black configuration to pyproject.toml (line-length=100)
- [ ] Add isort configuration to pyproject.toml (profile="black")
- [ ] Add ruff configuration to pyproject.toml (comprehensive linting rules)
- [ ] Add mypy configuration to pyproject.toml (strict mode)
- [ ] Add pytest + coverage configuration to pyproject.toml (≥75%)
- [ ] Document code style and pre-commit workflow in CONTRIBUTING.md

---

### Phase 1: Core Architecture (Plugin System Foundation)
**Goal**: Build plugin loading and core abstractions before any features

**Dependencies**: Requires Phase 0 completion

**Subphase 1.1: Plugin API Design** (Sequential - must complete first)
- [ ] 1.1.1 Design Pydantic base models for all data types
  - [ ] Define MetricData base class
  - [ ] Define SystemSnapshot model
  - [ ] Define PluginMetadata model
  - [ ] Write Pydantic model tests
- [ ] 1.1.2 Create plugin abstract base classes
  - [ ] PanePlugin ABC with collect_data/render_tui/get_schema
  - [ ] CollectorPlugin ABC
  - [ ] FormatterPlugin ABC
  - [ ] ActionPlugin ABC
  - [ ] Document plugin lifecycle in docstrings
- [ ] 1.1.3 Design plugin registration and discovery
  - [ ] Define entry points schema for setup.py
  - [ ] Create PluginRegistry class
  - [ ] Implement entry point scanning
  - [ ] Implement directory scanning
  - [ ] Add plugin dependency resolution

**Subphase 1.2: Plugin Loading System** (Depends on 1.1)

**Tasks can run in parallel**:
- [ ] 1.2.1 Entry point loader
  - [ ] Scan setuptools entry points
  - [ ] Validate plugin classes against ABCs
  - [ ] Handle import errors gracefully
  - [ ] Write unit tests for entry point loading

- [ ] 1.2.2 Directory loader
  - [ ] Scan ~/.uptop/plugins/ for .py files
  - [ ] Dynamic import of plugin modules
  - [ ] Handle module import errors
  - [ ] Write unit tests for directory loading

- [ ] 1.2.3 Plugin registry
  - [ ] Combine entry point and directory plugins
  - [ ] Detect plugin conflicts (duplicate names)
  - [ ] Plugin initialization with dependency injection
  - [ ] Plugin lifecycle management (init, start, stop)

- [ ] 1.2.4 Plugin error handling
  - [ ] Graceful handling of plugin load failures
  - [ ] Verbose logging for plugin issues
  - [ ] Plugin validation on load
  - [ ] Create PluginError exception hierarchy

**Subphase 1.3: Configuration System** (Can start in parallel with 1.2)

**Tasks can run in parallel**:
- [ ] 1.3.1 YAML config loading
  - [ ] Create Config Pydantic model matching schema
  - [ ] Implement config file discovery (~/.config/uptop/config.yaml)
  - [ ] Implement config loading with PyYAML
  - [ ] Add config validation with Pydantic
  - [ ] Handle missing config (use defaults)

- [ ] 1.3.2 Default configuration
  - [ ] Create default config as Python dict
  - [ ] Document all config options
  - [ ] Write config schema to JSON Schema for IDE support

- [ ] 1.3.3 CLI argument parsing
  - [ ] Setup Typer[all] (type-hint based CLI framework)
  - [ ] Implement hybrid mode detection (tui vs cli)
  - [ ] Implement config override from CLI flags
  - [ ] Add --config flag for custom config path

- [ ] 1.3.4 Environment variable support
  - [ ] Implement ${VAR} expansion in config values
  - [ ] Add UPTOP_CONFIG_PATH environment variable
  - [ ] Document env var usage

**Subphase 1.4: Data Collection Framework** (Depends on 1.1)

**Tasks can run in parallel**:
- [ ] 1.4.1 Create DataCollector base
  - [ ] Abstract collector interface
  - [ ] Async data collection support
  - [ ] Collection interval management
  - [ ] Error handling for collectors

- [ ] 1.4.2 In-memory data buffer
  - [ ] Ring buffer for historical data (configurable size)
  - [ ] Thread-safe access to data
  - [ ] Data expiration based on age
  - [ ] Memory usage limits

- [ ] 1.4.3 Collection scheduler
  - [ ] Per-pane interval scheduling
  - [ ] Async task management (asyncio)
  - [ ] Collection timeout handling
  - [ ] Performance monitoring (collection latency)

---

### Phase 2: Core Internal Plugins (Panes)
**Goal**: Implement all core monitoring panes as internal plugins

**Dependencies**: Requires Phase 1 completion (plugin system must exist)

**All subphases can run in PARALLEL** (independent feature branches):

**Subphase 2.1: CPU Pane Plugin** (`uptop.plugins.cpu`)
- [ ] 2.1.1 CPU data collection
  - [ ] Per-core usage via psutil.cpu_percent(percpu=True)
  - [ ] CPU frequency via psutil.cpu_freq(percpu=True)
  - [ ] Load averages via psutil.getloadavg()
  - [ ] CPU temperature via psutil.sensors_temperatures()
  - [ ] Define CPUData Pydantic model

- [ ] 2.1.2 CPU TUI rendering
  - [ ] Create Textual widget for CPU pane
  - [ ] Horizontal bar graphs for per-core usage
  - [ ] Sparkline graphs for historical data
  - [ ] Display freq and temp alongside usage

- [ ] 2.1.3 CPU plugin implementation
  - [ ] Implement CPUPane(PanePlugin)
  - [ ] Wire up data collection and rendering
  - [ ] Register via entry point
  - [ ] Write plugin tests

**Subphase 2.2: Memory Pane Plugin** (`uptop.plugins.memory`)
- [ ] 2.2.1 Memory data collection
  - [ ] Virtual memory via psutil.virtual_memory()
  - [ ] Swap memory via psutil.swap_memory()
  - [ ] Define MemoryData Pydantic model

- [ ] 2.2.2 Memory TUI rendering
  - [ ] Create Textual widget for memory pane
  - [ ] Progress bars for RAM and swap usage
  - [ ] Breakdown display (cached, buffers, etc.)

- [ ] 2.2.3 Memory plugin implementation
  - [ ] Implement MemoryPane(PanePlugin)
  - [ ] Register via entry point
  - [ ] Write plugin tests

**Subphase 2.3: Process Pane Plugin** (`uptop.plugins.processes`)
- [ ] 2.3.1 Process data collection
  - [ ] Process list via psutil.process_iter()
  - [ ] Collect PID, user, CPU%, MEM%, VSZ, RSS, state, runtime, command
  - [ ] Handle process access errors (permission denied)
  - [ ] Define ProcessData and ProcessList Pydantic models

- [ ] 2.3.2 Process detail collection
  - [ ] Open files via Process.open_files()
  - [ ] Network connections via Process.connections()
  - [ ] Threads via Process.threads()
  - [ ] Environment via Process.environ()

- [ ] 2.3.3 Process TUI rendering
  - [ ] Create Textual DataTable for process list
  - [ ] Sortable columns
  - [ ] Tree view mode (parent-child hierarchy)
  - [ ] Process detail panel widget

- [ ] 2.3.4 Process filtering
  - [ ] Implement smart filter (type-ahead search)
  - [ ] Implement preset filters (high CPU, high mem, my processes)
  - [ ] Filter evaluation engine

- [ ] 2.3.5 Process actions
  - [ ] Kill action (SIGTERM/SIGKILL)
  - [ ] Priority action (renice)
  - [ ] Confirmation dialogs for actions

- [ ] 2.3.6 Process plugin implementation
  - [ ] Implement ProcessPane(PanePlugin)
  - [ ] Register actions as ActionPlugins
  - [ ] Register via entry point
  - [ ] Write plugin tests

**Subphase 2.4: Network Pane Plugin** (`uptop.plugins.network`)
- [ ] 2.4.1 Network interface data collection
  - [ ] Interface stats via psutil.net_io_counters(pernic=True)
  - [ ] Calculate bandwidth rates (bytes/sec)
  - [ ] Define NetworkInterfaceData Pydantic model

- [ ] 2.4.2 Active connections collection
  - [ ] Connections via psutil.net_connections()
  - [ ] Connection state, local/remote addresses
  - [ ] Define ConnectionData Pydantic model

- [ ] 2.4.3 Per-process network (requires root)
  - [ ] Process network usage via Process.connections()
  - [ ] Aggregate per-process bandwidth
  - [ ] Handle permission errors gracefully

- [ ] 2.4.4 Network TUI rendering
  - [ ] Interface stats table
  - [ ] Bandwidth graphs (upload/download over time)
  - [ ] Active connections table
  - [ ] Per-process network table

- [ ] 2.4.5 Network plugin implementation
  - [ ] Implement NetworkPane(PanePlugin)
  - [ ] Register via entry point
  - [ ] Write plugin tests

**Subphase 2.5: Disk Pane Plugin** (`uptop.plugins.disk`)
- [ ] 2.5.1 Filesystem usage collection
  - [ ] Disk usage via psutil.disk_usage() per partition
  - [ ] List partitions via psutil.disk_partitions()
  - [ ] Define DiskUsageData Pydantic model

- [ ] 2.5.2 Disk I/O collection
  - [ ] Disk I/O via psutil.disk_io_counters(perdisk=True)
  - [ ] Calculate read/write rates, IOPS
  - [ ] Define DiskIOData Pydantic model

- [ ] 2.5.3 Per-process I/O (if available)
  - [ ] Process I/O via Process.io_counters()
  - [ ] Aggregate per-process disk usage

- [ ] 2.5.4 Disk TUI rendering
  - [ ] Filesystem usage table with progress bars
  - [ ] Disk I/O graphs (read/write rates)
  - [ ] Per-process I/O table

- [ ] 2.5.5 Disk plugin implementation
  - [ ] Implement DiskPane(PanePlugin)
  - [ ] Register via entry point
  - [ ] Write plugin tests

**Subphase 2.6: GPU Pane Plugin** (`uptop.plugins.gpu`)
- [ ] 2.6.1 NVIDIA GPU support
  - [ ] Install pynvml optional dependency
  - [ ] Detect NVIDIA GPUs
  - [ ] Collect utilization, memory, temp, power, fan via pynvml
  - [ ] Per-process GPU memory
  - [ ] Define NVIDIAGPUData Pydantic model

- [ ] 2.6.2 AMD GPU support
  - [ ] Install pyamdgpuinfo or use rocm-smi subprocess
  - [ ] Detect AMD GPUs
  - [ ] Collect utilization, VRAM, temp, clocks
  - [ ] Define AMDGPUData Pydantic model

- [ ] 2.6.3 Intel GPU support
  - [ ] Use intel_gpu_top subprocess
  - [ ] Parse output for usage and memory
  - [ ] Define IntelGPUData Pydantic model

- [ ] 2.6.4 Apple GPU support
  - [ ] Use Metal API via subprocess to system_profiler
  - [ ] Collect GPU activity, memory pressure
  - [ ] Define AppleGPUData Pydantic model

- [ ] 2.6.5 GPU TUI rendering
  - [ ] GPU table (one row per GPU)
  - [ ] Utilization and memory progress bars
  - [ ] Temperature and power display
  - [ ] Per-process GPU memory table

- [ ] 2.6.6 GPU plugin implementation
  - [ ] Implement GPUPane(PanePlugin)
  - [ ] Handle missing GPU gracefully
  - [ ] Register via entry point with optional dependencies
  - [ ] Write plugin tests (mock GPU APIs)

**Subphase 2.7: Sensors Pane Plugin** (`uptop.plugins.sensors`)
- [ ] 2.7.1 Sensor data collection
  - [ ] Temperatures via psutil.sensors_temperatures()
  - [ ] Fan speeds via psutil.sensors_fans()
  - [ ] Battery via psutil.sensors_battery() if applicable
  - [ ] Define SensorData Pydantic model

- [ ] 2.7.2 Sensor TUI rendering
  - [ ] Grouped display (temps, fans, battery)
  - [ ] Visual alerts for high temps (>80°C warning, >90°C critical)
  - [ ] Auto-hide missing sensor groups

- [ ] 2.7.3 Sensors plugin implementation
  - [ ] Implement SensorsPane(PanePlugin)
  - [ ] Handle missing sensors gracefully
  - [ ] Register via entry point
  - [ ] Write plugin tests

---

### Phase 3: TUI Implementation
**Goal**: Build interactive terminal UI using Textual

**Dependencies**: Requires Phase 1 (plugin system) and Phase 2.1-2.2 (at least CPU and memory panes for testing)

**Subphase 3.1: Textual Application Structure** (Sequential)
- [ ] 3.1.1 Main Textual app
  - [ ] Create UptopApp(App) class
  - [ ] Initialize plugin registry in app
  - [ ] Setup app lifecycle (startup, shutdown)
  - [ ] Handle SIGINT/SIGTERM gracefully

- [ ] 3.1.2 Main layout
  - [ ] Create grid layout for panes
  - [ ] Implement configurable pane positioning
  - [ ] Add header (title, current time, uptop version)
  - [ ] Add footer (keybinding hints)

- [ ] 3.1.3 Pane container widget
  - [ ] PaneContainer widget to wrap plugin panes
  - [ ] Pane title bar with name and refresh interval
  - [ ] Pane error display for failed data collection
  - [ ] Pane loading indicator

**Subphase 3.2: Keyboard & Mouse Handling** (Can run in parallel with 3.3)
- [ ] 3.2.1 Core keybindings
  - [ ] Quit (q), Help (?), Refresh (r)
  - [ ] Navigate between panes (tab, arrow keys)
  - [ ] Focus pane for interaction

- [ ] 3.2.2 Process pane keybindings
  - [ ] Filter (/), Sort (s), Kill (k), Priority (n), Tree view (t)
  - [ ] Up/down to select process
  - [ ] Enter to show process detail

- [ ] 3.2.3 Configurable keybindings
  - [ ] Load keybindings from config
  - [ ] Allow user to rebind keys
  - [ ] Display active keybindings in help screen

- [ ] 3.2.4 Mouse support
  - [ ] Click to select panes
  - [ ] Click to select processes
  - [ ] Scroll in process list
  - [ ] Drag to resize panes (if feasible in Textual)

**Subphase 3.3: Theming System** (Can run in parallel with 3.2)
- [ ] 3.3.1 Theme infrastructure
  - [ ] Load Textual CSS themes
  - [ ] Built-in themes: dark, light, solarized, nord, gruvbox
  - [ ] Theme switching at runtime

- [ ] 3.3.2 Custom theme support
  - [ ] Load custom CSS from config
  - [ ] Validate custom theme files
  - [ ] Document theme variables

- [ ] 3.3.3 Color palette for data
  - [ ] CPU usage colors (green < 50%, yellow 50-80%, red > 80%)
  - [ ] Memory usage colors
  - [ ] Temperature alert colors
  - [ ] Process state colors

**Subphase 3.4: Layout Management** (Depends on 3.1)
- [ ] 3.4.1 Layout presets
  - [ ] Implement layout switching
  - [ ] Built-in layouts: standard, server_focus, dev_focus
  - [ ] Save current layout as preset (command: `:save-layout`)

- [ ] 3.4.2 Dynamic layout
  - [ ] Resize panes with keyboard shortcuts
  - [ ] Rearrange panes (if feasible)
  - [ ] Toggle pane visibility

- [ ] 3.4.3 Layout configuration
  - [ ] Load layout from config
  - [ ] Validate layout against available panes
  - [ ] Fall back to default layout on error

**Subphase 3.5: In-Memory History & Graphs** (Can run in parallel)
- [ ] 3.5.1 Historical data buffer
  - [ ] Ring buffer per pane (last N data points)
  - [ ] Configurable history size (default 60 points = 1 minute at 1s interval)
  - [ ] Efficient memory management

- [ ] 3.5.2 Sparkline/graph rendering
  - [ ] CPU usage sparklines per core
  - [ ] Network bandwidth graphs
  - [ ] Disk I/O graphs
  - [ ] Use Textual's plotting widgets or custom rendering

---

### Phase 4: CLI Mode & Formatters
**Goal**: Implement command-line mode with structured output formats

**Dependencies**: Requires Phase 1 (plugin system) and Phase 2 (all panes for data collection)

**All subphases can run in PARALLEL**:

**Subphase 4.1: JSON Formatter** (`uptop.formatters.json_fmt`)
- [ ] 4.1.1 JSON serialization
  - [ ] Convert all Pydantic models to JSON
  - [ ] Handle datetime serialization (ISO 8601)
  - [ ] Pretty-print vs compact JSON (configurable)

- [ ] 4.1.2 JSON formatter plugin
  - [ ] Implement JSONFormatter(FormatterPlugin)
  - [ ] Register with --json flag
  - [ ] Write tests with snapshot testing

- [ ] 4.1.3 Streaming JSON output
  - [ ] Output JSON objects separated by newlines (JSONL)
  - [ ] Ensure valid JSON per interval

**Subphase 4.2: Markdown Formatter** (`uptop.formatters.markdown_fmt`)
- [ ] 4.2.1 Markdown table generation
  - [ ] Convert pane data to GFM tables
  - [ ] Format numbers with appropriate precision
  - [ ] Section headers per pane

- [ ] 4.2.2 Markdown formatter plugin
  - [ ] Implement MarkdownFormatter(FormatterPlugin)
  - [ ] Register with --markdown flag
  - [ ] Write tests with snapshot testing

**Subphase 4.3: Prometheus Formatter** (`uptop.formatters.prometheus_fmt`)
- [ ] 4.3.1 Prometheus metrics generation
  - [ ] Convert pane data to Prometheus exposition format
  - [ ] Add HELP and TYPE comments
  - [ ] Include labels (core, interface, disk, etc.)

- [ ] 4.3.2 Prometheus formatter plugin
  - [ ] Implement PrometheusFormatter(FormatterPlugin)
  - [ ] Register with --prometheus flag
  - [ ] Write tests with snapshot testing

- [ ] 4.3.3 Prometheus metric naming
  - [ ] Follow Prometheus naming conventions
  - [ ] Namespace all metrics with uptop_ prefix
  - [ ] Document metric meanings

**Subphase 4.4: CLI Output Modes** (Depends on 4.1-4.3)
- [ ] 4.4.1 Single snapshot mode (--once)
  - [ ] Collect data once
  - [ ] Format and output
  - [ ] Exit

- [ ] 4.4.2 Streaming mode (--stream)
  - [ ] Loop: collect, format, output
  - [ ] Respect --interval flag
  - [ ] Handle SIGINT for clean exit

- [ ] 4.4.3 Continuous mode (--continuous)
  - [ ] Clear screen and redraw (ANSI escape codes)
  - [ ] Update in-place like watch command
  - [ ] Respect --interval flag

**Subphase 4.5: Query & Aggregation** (Can run in parallel)
- [ ] 4.5.1 JMESPath integration
  - [ ] Add jmespath library dependency
  - [ ] Implement -q/--query flag
  - [ ] Apply query to JSON output
  - [ ] Handle query errors gracefully

- [ ] 4.5.2 Aggregation engine
  - [ ] Implement --aggregate flag (avg, min, max, sum)
  - [ ] Implement --duration flag (collection window)
  - [ ] Collect data over duration
  - [ ] Calculate aggregations per metric
  - [ ] Output aggregated result

**Subphase 4.6: Help System** (Can run in parallel)
- [ ] 4.6.1 Standard help
  - [ ] Comprehensive --help output with Click/Typer
  - [ ] Usage examples in help
  - [ ] Document all flags and modes

- [ ] 4.6.2 AI help (dashdash integration)
  - [ ] Integrate dashdash pattern (https://github.com/visionik/dashdash)
  - [ ] Implement --ai-help flag
  - [ ] Connect to LLM API for natural language Q&A
  - [ ] Provide uptop-specific context to LLM
  - [ ] Handle API errors gracefully

---

### Phase 5: Example Plugins
**Goal**: Create example plugins to demonstrate plugin system

**Dependencies**: Requires Phase 1 (plugin system), Phase 3 (TUI for testing), Phase 4 (formatters)

**All subphases can run in PARALLEL** (separate packages):

**Subphase 5.1: Docker Plugin** (`uptop-plugin-docker` package)
- [ ] 5.1.1 Docker data collection
  - [ ] Use docker Python SDK
  - [ ] List running containers
  - [ ] Get container stats (CPU, memory, network)
  - [ ] Define DockerContainerData Pydantic model

- [ ] 5.1.2 Docker TUI rendering
  - [ ] Container table (name, ID, CPU%, MEM%, status)
  - [ ] Container detail view

- [ ] 5.1.3 Docker plugin package
  - [ ] Create separate repo/package: uptop-plugin-docker
  - [ ] Implement DockerPane(PanePlugin)
  - [ ] Setup entry point: uptop.panes = docker:DockerPane
  - [ ] Write plugin README and tests
  - [ ] Publish to PyPI

**Subphase 5.2: Custom Pane Example** (`uptop.plugins.hello_world`)
- [ ] 5.2.1 Minimal hello world pane
  - [ ] Simple data model (HelloData with message)
  - [ ] Trivial data collection (return "Hello, World!")
  - [ ] Basic rendering

- [ ] 5.2.2 Extensive documentation
  - [ ] Heavily commented code
  - [ ] Step-by-step tutorial in docs
  - [ ] Include in plugin dev guide

**Subphase 5.3: Weather Plugin** (`uptop-plugin-weather` package)
- [ ] 5.3.1 Weather API integration
  - [ ] Use weather API (OpenWeatherMap, wttr.in, etc.)
  - [ ] Fetch weather for configured location
  - [ ] Cache results (10 minute TTL)
  - [ ] Define WeatherData Pydantic model

- [ ] 5.3.2 Weather TUI rendering
  - [ ] Display temp, conditions, humidity, wind
  - [ ] Weather icons (ASCII art or unicode)

- [ ] 5.3.3 Weather plugin package
  - [ ] Create separate repo/package: uptop-plugin-weather
  - [ ] Implement WeatherPane(PanePlugin)
  - [ ] Setup entry point
  - [ ] Write plugin README and tests
  - [ ] Publish to PyPI

**Subphase 5.4: Log Monitor Plugin** (`uptop-plugin-logmon` package)
- [ ] 5.4.1 Log file tailing
  - [ ] Tail log file(s) specified in config
  - [ ] Regex filtering
  - [ ] Syntax highlighting (error, warning, info)
  - [ ] Define LogEntry Pydantic model

- [ ] 5.4.2 Log TUI rendering
  - [ ] Scrollable log view
  - [ ] Highlighted matches
  - [ ] Filter input box

- [ ] 5.4.3 Log monitor plugin package
  - [ ] Create separate repo/package: uptop-plugin-logmon
  - [ ] Implement LogMonitorPane(PanePlugin)
  - [ ] Setup entry point
  - [ ] Write plugin README and tests
  - [ ] Publish to PyPI

---

### Phase 6: Testing & Quality Assurance
**Goal**: Comprehensive test coverage and quality assurance

**Dependencies**: Requires all feature phases (1-5) to be substantially complete

**Subphase 6.1: Unit Tests** (Can start in parallel with feature development)
- [ ] 6.1.1 Plugin system tests
  - [ ] Test plugin loading (entry points, directory)
  - [ ] Test plugin registry
  - [ ] Test plugin error handling
  - [ ] Mock plugins for testing

- [ ] 6.1.2 Data model tests
  - [ ] Test all Pydantic models
  - [ ] Test validation rules
  - [ ] Test serialization/deserialization

- [ ] 6.1.3 Collector tests
  - [ ] Mock psutil for deterministic tests
  - [ ] Test data collection logic
  - [ ] Test error handling in collectors

- [ ] 6.1.4 Formatter tests
  - [ ] Test JSON formatter output
  - [ ] Test Markdown formatter output
  - [ ] Test Prometheus formatter output
  - [ ] Snapshot testing for formatters

**Subphase 6.2: Integration Tests** (Depends on Phase 3 and 4 completion)
- [ ] 6.2.1 CLI mode integration tests
  - [ ] Test full workflow: data collection -> formatting -> output
  - [ ] Test --once, --stream, --continuous modes
  - [ ] Test query and aggregation

- [ ] 6.2.2 Plugin loading integration tests
  - [ ] Test loading real plugins (example plugins)
  - [ ] Test plugin isolation (one plugin failure doesn't crash app)

- [ ] 6.2.3 Configuration integration tests
  - [ ] Test config loading and merging (file + CLI flags)
  - [ ] Test environment variable expansion
  - [ ] Test invalid config handling

**Subphase 6.3: Snapshot Tests** (Can run in parallel)
- [ ] 6.3.1 Formatter snapshots
  - [ ] Capture JSON output and compare to golden file
  - [ ] Capture Markdown output
  - [ ] Capture Prometheus output

- [ ] 6.3.2 Update snapshot workflow
  - [ ] Document how to update snapshots
  - [ ] Add pytest flag for snapshot update

**Subphase 6.4: Manual TUI Testing** (Requires Phase 3 completion)
- [ ] 6.4.1 TUI test procedures document
  - [ ] Create manual test checklist
  - [ ] Keyboard navigation tests
  - [ ] Mouse interaction tests
  - [ ] Theme switching tests
  - [ ] Layout switching tests

- [ ] 6.4.2 Visual regression testing (optional)
  - [ ] Use Textual snapshot testing if available
  - [ ] Capture terminal screenshots for comparison

**Subphase 6.5: Performance Testing** (Can run in parallel)
- [ ] 6.5.1 Performance benchmarks
  - [ ] Measure data collection time per pane
  - [ ] Measure formatter performance
  - [ ] Measure plugin loading time

- [ ] 6.5.2 Resource usage testing
  - [ ] Measure uptop's own CPU usage
  - [ ] Measure uptop's own memory usage
  - [ ] Ensure <5% CPU and <100MB RAM under normal use

- [ ] 6.5.3 Stress testing
  - [ ] Test with 1000+ processes
  - [ ] Test with many network connections
  - [ ] Test with multiple GPUs

**Subphase 6.6: Cross-Platform Testing** (Depends on CI setup in Phase 0)
- [ ] 6.6.1 Linux testing
  - [ ] Test on Ubuntu 22.04, 24.04
  - [ ] Test on Debian 12
  - [ ] Test on Fedora 39

- [ ] 6.6.2 macOS testing
  - [ ] Test on macOS 13 (Ventura)
  - [ ] Test on macOS 14 (Sonoma)
  - [ ] Test Apple Silicon and Intel Macs

- [ ] 6.6.3 Permission scenarios
  - [ ] Test as normal user
  - [ ] Test with sudo for privileged features
  - [ ] Test permission error handling

---

### Phase 7: Documentation
**Goal**: Comprehensive user and developer documentation

**Dependencies**: Requires feature completion (Phases 1-5) for accurate documentation

**Subphase 7.1: User Documentation** (Can start in parallel with feature dev, updated as features land)
- [ ] 7.1.1 README.md
  - [ ] Project description and goals
  - [ ] Quick start guide
  - [ ] Installation instructions (pip, brew, apt)
  - [ ] Usage examples (TUI and CLI)
  - [ ] Screenshots/demo GIFs
  - [ ] Link to full documentation

- [ ] 7.1.2 Installation guide
  - [ ] pip install uptop
  - [ ] Optional dependencies: uptop[gpu], uptop[all]
  - [ ] Package manager installation (brew, apt, dnf)
  - [ ] Building from source

- [ ] 7.1.3 User guide
  - [ ] TUI usage: navigation, keybindings, actions
  - [ ] CLI usage: modes, formats, flags
  - [ ] Configuration file reference
  - [ ] Customization: themes, layouts, keybindings

- [ ] 7.1.4 CLI reference
  - [ ] All command-line flags documented
  - [ ] Usage examples for common scenarios
  - [ ] Query syntax examples
  - [ ] Aggregation examples

**Subphase 7.2: Plugin Developer Guide** (Can start after Phase 1 completion)
- [ ] 7.2.1 Plugin development tutorial
  - [ ] Step-by-step: create a custom pane plugin
  - [ ] Explain plugin lifecycle
  - [ ] Explain data collection vs rendering
  - [ ] Using Pydantic models

- [ ] 7.2.2 Plugin API reference
  - [ ] Document all ABCs (PanePlugin, CollectorPlugin, etc.)
  - [ ] Document Pydantic base models
  - [ ] Document plugin registration (entry points, directory)
  - [ ] Code examples for each plugin type

- [ ] 7.2.3 Example plugin walkthroughs
  - [ ] Annotated hello_world plugin
  - [ ] Annotated Docker plugin
  - [ ] Annotated weather plugin
  - [ ] Annotated log monitor plugin

- [ ] 7.2.4 Plugin best practices
  - [ ] Error handling
  - [ ] Performance considerations
  - [ ] Security considerations (user trust model)
  - [ ] Testing plugins

**Subphase 7.3: Man Pages** (Can run in parallel with 7.1)
- [ ] 7.3.1 uptop(1) man page
  - [ ] Synopsis, description, options
  - [ ] Examples section
  - [ ] Files section (config locations)
  - [ ] See also section

- [ ] 7.3.2 uptop.yaml(5) man page
  - [ ] Configuration file format
  - [ ] All configuration options documented
  - [ ] Examples

- [ ] 7.3.3 Man page generation
  - [ ] Use click-man or similar to generate from Click/Typer
  - [ ] Include man pages in package distribution

**Subphase 7.4: Website (mkdocs)** (Can run in parallel with 7.1-7.3)
- [ ] 7.4.1 mkdocs setup
  - [ ] Install mkdocs-material theme
  - [ ] Configure mkdocs.yml
  - [ ] Setup GitHub Pages deployment

- [ ] 7.4.2 Website content
  - [ ] Home page (project overview, features, demo)
  - [ ] Installation page
  - [ ] User guide (multi-page)
  - [ ] Plugin developer guide (multi-page)
  - [ ] API reference (auto-generated from docstrings)
  - [ ] Plugin gallery (curated list)

- [ ] 7.4.3 Code reference docs
  - [ ] Use mkdocstrings to generate API docs from code
  - [ ] Document all public APIs
  - [ ] Link from plugin dev guide to API reference

**Subphase 7.5: Community Documentation** (Can run in parallel)
- [ ] 7.5.1 CONTRIBUTING.md
  - [ ] Development setup instructions
  - [ ] Code style guidelines (ruff, mypy, black)
  - [ ] Commit message conventions
  - [ ] PR process
  - [ ] Testing requirements

- [ ] 7.5.2 Issue templates
  - [ ] Bug report template
  - [ ] Feature request template
  - [ ] Plugin idea template

- [ ] 7.5.3 PR template
  - [ ] Checklist: tests, docs, changelog
  - [ ] Description prompts

- [ ] 7.5.4 Plugin registry
  - [ ] Create awesome-uptop repository or page
  - [ ] Curated list of community plugins
  - [ ] Submission guidelines

---

### Phase 8: Packaging & Distribution
**Goal**: Package uptop for easy installation and distribution

**Dependencies**: Requires core features complete (Phases 1-4), documentation (Phase 7)

**Subphase 8.1: PyPI Package** (Can start in parallel with Phase 7)
- [ ] 8.1.1 Package metadata
  - [ ] Complete pyproject.toml with all metadata
  - [ ] Keywords, classifiers, URLs
  - [ ] Entry points for CLI (uptop command)
  - [ ] Include all package data (default config, themes)

- [ ] 8.1.2 Dependencies specification
  - [ ] Core dependencies: psutil, textual, click/typer, pydantic, pyyaml
  - [ ] Optional dependencies:
    - [ ] uptop[gpu]: pynvml, pyamdgpuinfo
    - [ ] uptop[query]: jmespath
    - [ ] uptop[all]: all optional deps

- [ ] 8.1.3 Build and publish workflow
  - [ ] Create GitHub Action for PyPI publish on release
  - [ ] Test PyPI upload first
  - [ ] Setup PyPI API token
  - [ ] Publish to PyPI

**Subphase 8.2: Package Managers** (Can run in parallel with 8.1)
- [ ] 8.2.1 Homebrew formula (macOS/Linux)
  - [ ] Create homebrew-uptop tap
  - [ ] Write uptop.rb formula
  - [ ] Test installation via brew
  - [ ] Submit to homebrew-core (optional, later)

- [ ] 8.2.2 APT repository (Debian/Ubuntu)
  - [ ] Create .deb package
  - [ ] Setup APT repository (GitHub Pages or similar)
  - [ ] Document installation via apt

- [ ] 8.2.3 RPM repository (Fedora/RHEL)
  - [ ] Create .rpm package
  - [ ] Setup RPM repository
  - [ ] Document installation via dnf/yum

**Subphase 8.3: Release Process** (Can run in parallel)
- [ ] 8.3.1 Versioning strategy
  - [ ] Semantic versioning (semver)
  - [ ] Version bumping script
  - [ ] Git tagging convention

- [ ] 8.3.2 Changelog automation
  - [ ] Use conventional commits
  - [ ] Auto-generate CHANGELOG.md
  - [ ] Include changelog in releases

- [ ] 8.3.3 Release checklist
  - [ ] Document release process in CONTRIBUTING.md
  - [ ] Checklist: version bump, changelog, tests pass, docs updated
  - [ ] GitHub release creation with notes

---

### Phase 9: Polish & Launch Preparation
**Goal**: Final polish, performance optimization, and launch readiness

**Dependencies**: Requires all previous phases substantially complete

**Subphase 9.1: Performance Optimization** (Can run in parallel)
- [ ] 9.1.1 Profiling
  - [ ] Profile data collection with cProfile
  - [ ] Identify bottlenecks
  - [ ] Optimize hot paths

- [ ] 9.1.2 Memory optimization
  - [ ] Optimize in-memory buffer size
  - [ ] Reduce object allocations
  - [ ] Profile with memory_profiler

- [ ] 9.1.3 Startup time optimization
  - [ ] Lazy load plugins
  - [ ] Defer expensive imports
  - [ ] Measure and optimize startup time

**Subphase 9.2: Error Handling & Logging** (Can run in parallel)
- [ ] 9.2.1 Comprehensive error messages
  - [ ] Review all user-facing errors
  - [ ] Add actionable suggestions to errors
  - [ ] Test error scenarios

- [ ] 9.2.2 Logging refinement
  - [ ] Ensure consistent log levels
  - [ ] Add debug logging for troubleshooting
  - [ ] Test verbose mode

- [ ] 9.2.3 Graceful degradation verification
  - [ ] Test each pane failure independently
  - [ ] Verify app continues running
  - [ ] Test missing dependencies

**Subphase 9.3: UX Polish** (Can run in parallel)
- [ ] 9.3.1 TUI visual polish
  - [ ] Consistent spacing and alignment
  - [ ] Smooth animations (if any)
  - [ ] Polish themes
  - [ ] Responsive layout on terminal resize

- [ ] 9.3.2 Help and onboarding
  - [ ] Help screen polish
  - [ ] Keybinding hints in footer
  - [ ] First-run experience (optional tutorial)

- [ ] 9.3.3 CLI output polish
  - [ ] Consistent formatting
  - [ ] Pretty-print JSON by default
  - [ ] Colorize output in TTY (optional)

**Subphase 9.4: Security Review** (Can run in parallel)
- [ ] 9.4.1 Dependency audit
  - [ ] Run pip-audit or safety
  - [ ] Update dependencies to latest secure versions
  - [ ] Document known vulnerabilities if any

- [ ] 9.4.2 Code security review
  - [ ] Review subprocess calls (command injection risk)
  - [ ] Review file I/O (path traversal risk)
  - [ ] Review plugin loading (arbitrary code execution - expected)

- [ ] 9.4.3 Security documentation
  - [ ] Document plugin trust model
  - [ ] Security best practices for plugin developers
  - [ ] Responsible disclosure policy

**Subphase 9.5: Launch Assets** (Can run in parallel)
- [ ] 9.5.1 Demo materials
  - [ ] Record demo GIFs/videos of TUI
  - [ ] Record demo of CLI usage
  - [ ] Create screenshots for docs

- [ ] 9.5.2 Launch announcement
  - [ ] Write launch blog post or README section
  - [ ] Prepare HackerNews/Reddit posts
  - [ ] Social media posts (if applicable)

- [ ] 9.5.3 Community setup
  - [ ] Enable GitHub Discussions
  - [ ] Create initial discussion topics
  - [ ] Pin welcome message

---

## Dependencies Map

### External Dependencies (Python Packages)

**Core (required)**:
- `python >= 3.11` - Modern Python features
- `psutil >= 5.9.0` - System metrics collection
- `textual[dev] >= 0.40.0` - TUI framework with dev tools
- `typer[all] >= 0.9.0` - CLI framework (type-hint based)
- `pydantic >= 2.0.0` - Data validation and models
- `PyYAML >= 6.0` - YAML config parsing

**Optional**:
- `pynvml` - NVIDIA GPU monitoring (uptop[gpu])
- `pyamdgpuinfo` - AMD GPU monitoring (uptop[gpu])
- `jmespath` - Query syntax (uptop[query])
- `docker` - Docker plugin (uptop-plugin-docker)
- `requests` - Weather plugin (uptop-plugin-weather)

**Development**:
- `pytest >= 7.4` - Testing framework
- `pytest-cov >= 4.1` - Coverage reporting
- `pytest-mock >= 3.12` - Mocking support
- `pytest-asyncio` - Async test support
- `pytest-snapshot` - Snapshot testing
- `black >= 23` - Code formatting
- `isort >= 5.12` - Import sorting
- `ruff >= 0.1` - Linting
- `mypy >= 1.7` - Type checking

**Documentation**:
- `mkdocs-material` - Documentation site
- `mkdocstrings[python]` - API docs from docstrings
- `click-man` - Man page generation

### System Dependencies

**Linux**:
- `/proc` filesystem for detailed process info
- `nvidia-smi` for NVIDIA GPU (optional)
- `rocm-smi` for AMD GPU (optional)
- `intel_gpu_top` for Intel GPU (optional)

**macOS**:
- `system_profiler` for Apple GPU info
- `sysctl` for some system metrics

---

## Testing Strategy

### Unit Tests
- **Target**: ≥75% code coverage overall AND per-module (mandatory)
- **Scope**: Individual functions, classes, Pydantic models
- **Tools**: pytest, pytest-asyncio, pytest-mock
- **Mocking**: Mock psutil, subprocess, file I/O
- **Exclusions**: Exclude `__main__` and entry points from coverage

### Integration Tests
- **Scope**: End-to-end workflows (data collection → formatting → output)
- **Tools**: pytest with real plugin loading
- **Coverage**: All CLI modes, all formatters, plugin loading

### Snapshot Tests
- **Scope**: Formatter output (JSON, Markdown, Prometheus)
- **Tools**: pytest-snapshot
- **Process**: Capture golden files, compare on subsequent runs

### Manual TUI Tests
- **Scope**: Visual appearance, keyboard/mouse interaction, theming
- **Process**: Documented manual test checklist
- **Frequency**: Before each release

### Performance Tests
- **Metrics**: CPU usage, memory usage, collection latency
- **Targets**: <5% CPU, <100MB RAM, <100ms collection time per pane
- **Tools**: pytest-benchmark, memory_profiler, cProfile

### Cross-Platform Tests
- **Platforms**: Ubuntu 22.04, Ubuntu 24.04, Debian 12, Fedora 39, macOS 13, macOS 14
- **CI**: GitHub Actions matrix testing
- **Coverage**: All core features on all platforms

---

## Success Criteria

### Functionality
- [ ] All core panes working: CPU, Memory, Processes, Network, Disk, GPU, Sensors
- [ ] TUI mode fully interactive with keyboard and mouse
- [ ] CLI mode with JSON, Markdown, Prometheus output
- [ ] Plugin system supports entry points and directory plugins
- [ ] Example plugins demonstrate all plugin types
- [ ] Configuration system supports YAML and CLI overrides

### Performance
- [ ] uptop uses <5% CPU during monitoring
- [ ] uptop uses <100MB RAM
- [ ] Data collection latency <100ms per pane
- [ ] Startup time <2 seconds

### Quality
- [ ] ≥75% test coverage overall AND per-module
- [ ] All CI checks passing (tests, linting, type checking)
- [ ] `task check` passes before all commits
- [ ] No critical security vulnerabilities
- [ ] Documentation complete (user guide, plugin dev guide, API reference)
- [ ] All files < 1000 lines (preferably < 500 lines)

### Distribution
- [ ] Published to PyPI
- [ ] Available via Homebrew (macOS)
- [ ] Available via APT (Debian/Ubuntu)
- [ ] Available via DNF (Fedora)

### Community
- [ ] GitHub repository with contributing guide
- [ ] Issue and PR templates
- [ ] Plugin registry (awesome-uptop)
- [ ] GitHub Discussions enabled

---

## Open Questions & Decisions Needed

### Phase 3:
- [ ] **Pane resizing in Textual**: Is drag-to-resize feasible? (Research needed in Phase 3.4.2)
  - May be limited by Textual's capabilities
  - Fallback: Keyboard shortcuts for resize

### Phase 4:
- [ ] **AI help implementation**: Which LLM API to use for --ai-help? (Decision needed in Phase 4.6.2)
  - Options: OpenAI, Anthropic Claude, local LLM (ollama)
  - Consider user privacy and API costs
  - May need API key configuration

### Phase 5:
- [ ] **Weather API choice**: Which weather API for weather plugin? (Decision needed in Phase 5.3.1)
  - Options: OpenWeatherMap (requires API key), wttr.in (free, no key)
  - Preference: wttr.in for simplicity

### Phase 6:
- [ ] **Textual snapshot testing**: Does Textual have built-in snapshot testing? (Research needed in Phase 6.4.2)
  - Check Textual documentation for testing utilities
  - May need custom screenshot comparison

### Phase 8:
- [ ] **Package manager priorities**: Which package managers first? (Decision needed in Phase 8.2)
  - Priority: Homebrew (widest reach), then APT, then RPM
  - Can defer less common package managers

---

## Timeline Considerations

This specification is designed for **parallel development by multiple coding agents**. Here's how phases can overlap:

### Immediate Start (No dependencies):
- **Phase 0**: All tasks (repository, CI, docs structure, etc.)

### After Phase 0:
- **Phase 1**: Core architecture (plugin system, config, data collection framework)

### After Phase 1:
- **Phase 2**: All pane plugins (2.1-2.7) **IN PARALLEL** on feature branches
- **Phase 3**: TUI implementation (can start with partial Phase 2)
- **Phase 4**: CLI mode **IN PARALLEL** with Phase 3
- **Phase 5**: Example plugins **IN PARALLEL** with Phases 3-4

### Continuous (throughout):
- **Phase 6**: Testing (unit tests alongside feature dev, integration tests after features land)
- **Phase 7**: Documentation (user docs as features land, plugin dev guide after Phase 1)

### Final Phases:
- **Phase 8**: Packaging (after core features complete)
- **Phase 9**: Polish (after all features substantially complete)

### Estimated Parallelization:
- **Phase 0**: 1 agent, 1 week
- **Phase 1**: 3-4 agents (plugin API, config, data framework in parallel), 2-3 weeks
- **Phase 2**: 7 agents (one per pane), 2-3 weeks
- **Phase 3**: 4 agents (app structure, keyboard, theming, layout in parallel), 2-3 weeks
- **Phase 4**: 4 agents (formatters in parallel), 2 weeks
- **Phase 5**: 4 agents (one per example plugin), 1-2 weeks
- **Phase 6**: 2-3 agents (unit, integration, performance tests), ongoing
- **Phase 7**: 2 agents (user docs, plugin dev guide), ongoing
- **Phase 8**: 1-2 agents, 1 week
- **Phase 9**: 2-3 agents, 1-2 weeks

**Total estimated time with parallelization**: 8-12 weeks

---

## License & Contribution

- **License**: MIT
- **Contribution**: Open to community contributions via GitHub
- **Plugin ecosystem**: Encourage community plugins via plugin registry
- **Governance**: Benevolent dictator model initially, may evolve

---

## Appendices

### A. Example Configuration File

See Section 4.1 for complete example `~/.config/uptop/config.yaml`

### B. Plugin API Quick Reference

See Section 3.2 for complete plugin API examples

### C. Keyboard Shortcuts Reference

**Global**:
- `q`: Quit
- `?`: Help
- `r`: Refresh
- `Tab`: Next pane
- `Shift+Tab`: Previous pane

**Process Pane**:
- `/`: Filter
- `s`: Sort
- `k`: Kill process
- `n`: Change priority
- `t`: Toggle tree view
- `Enter`: Process detail

**Configurable** via `config.yaml` under `tui.keybindings`

### D. Prometheus Metrics Reference

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| uptop_cpu_usage_percent | gauge | core | CPU usage per core (0-100) |
| uptop_cpu_freq_mhz | gauge | core | CPU frequency in MHz |
| uptop_cpu_temp_celsius | gauge | core | CPU temperature in Celsius |
| uptop_memory_bytes | gauge | type (total/used/free/cached) | Memory in bytes |
| uptop_swap_bytes | gauge | type (total/used/free) | Swap in bytes |
| uptop_network_bytes_total | counter | interface, direction (sent/received) | Network bytes |
| uptop_network_packets_total | counter | interface, direction | Network packets |
| uptop_disk_usage_bytes | gauge | mountpoint, type (total/used/free) | Disk usage |
| uptop_disk_io_bytes_total | counter | disk, direction (read/write) | Disk I/O bytes |
| uptop_gpu_usage_percent | gauge | gpu_id, vendor | GPU utilization |
| uptop_gpu_memory_bytes | gauge | gpu_id, vendor, type (total/used) | GPU memory |
| uptop_gpu_temp_celsius | gauge | gpu_id, vendor | GPU temperature |
| uptop_process_count | gauge | state (running/sleeping/stopped) | Process count by state |

### E. Plugin Entry Point Schema

```python
# In plugin's setup.py or pyproject.toml:
entry_points={
    'uptop.panes': [
        'plugin_name = package.module:PaneClass',
    ],
    'uptop.collectors': [
        'plugin_name = package.module:CollectorClass',
    ],
    'uptop.formatters': [
        'format_name = package.module:FormatterClass',
    ],
    'uptop.actions': [
        'action_name = package.module:ActionClass',
    ],
}
```

### F. Data Model Examples

**CPUData**:
```python
from pydantic import BaseModel

class CPUCore(BaseModel):
    id: int
    usage_percent: float
    freq_mhz: float
    temp_celsius: float | None = None

class CPUData(BaseModel):
    cores: list[CPUCore]
    load_avg_1min: float
    load_avg_5min: float
    load_avg_15min: float
```

**ProcessData**:
```python
class ProcessData(BaseModel):
    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_mb: float
    vsz_kb: int
    rss_kb: int
    state: str  # running, sleeping, stopped, zombie
    runtime_seconds: float
    cmdline: str
```

### G. pyproject.toml Example

Complete `pyproject.toml` following Warp standards:

```toml
[project]
name = "uptop"
version = "0.1.0"
description = "Universal Performance & Telemetry Output - CLI+TUI system monitor"
authors = [{name = "Your Name", email = "you@example.com"}]
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
keywords = ["monitoring", "system", "performance", "cli", "tui", "btop"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: System :: Monitoring",
    "Topic :: System :: Systems Administration",
]

dependencies = [
    "psutil>=5.9.0",
    "textual[dev]>=0.40.0",
    "typer[all]>=0.9.0",
    "pydantic>=2.0.0",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
gpu = ["pynvml", "pyamdgpuinfo"]
query = ["jmespath"]
all = ["uptop[gpu,query]"]
dev = [
    "pytest>=7.4",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
    "pytest-asyncio",
    "pytest-snapshot",
    "black>=23",
    "isort>=5.12",
    "ruff>=0.1",
    "mypy>=1.7",
]

[project.scripts]
uptop = "uptop.__main__:main"

[project.urls]
Homepage = "https://github.com/yourusername/uptop"
Documentation = "https://uptop.readthedocs.io"
Repository = "https://github.com/yourusername/uptop"
Issues = "https://github.com/yourusername/uptop/issues"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "--cov=src --cov-report=html --cov-report=term-missing"

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/venv/*",
    "*/.venv/*",
    "*/__main__.py",  # Exclude entry points
]

[tool.coverage.report]
fail_under = 75
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.ruff]
line-length = 100
target-version = "py311"
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "W",    # pycodestyle warnings
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "DTZ",  # flake8-datetimez
    "T10",  # flake8-debugger
    "PIE",  # flake8-pie
    "PT",   # flake8-pytest-style
    "RET",  # flake8-return
    "SIM",  # flake8-simplify
]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = false
disallow_subclassing_any = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true
```

### H. Taskfile.yml Example

Complete `Taskfile.yml` following Warp standards:

```yaml
version: '3'

set:
  - errexit
  - nounset
  - pipefail

tasks:
  default:
    desc: List all available tasks
    cmds:
      - task --list
    silent: true

  install:
    desc: Install dependencies
    cmds:
      - pip install -e ".[dev]"

  fmt:
    desc: Format code (black, isort)
    cmds:
      - black src tests
      - isort src tests

  lint:
    desc: Lint code (ruff)
    cmds:
      - ruff check src tests

  type:
    desc: Type check (mypy)
    cmds:
      - mypy src

  test:
    desc: Run tests
    cmds:
      - pytest tests/

  test:coverage:
    desc: Run tests with coverage (≥75%)
    cmds:
      - pytest --cov=src --cov-report=html --cov-report=term-missing tests/
      - echo "Coverage report generated in htmlcov/index.html"

  quality:
    desc: Run all quality checks
    deps:
      - fmt
      - lint
      - type

  check:
    desc: Pre-commit checks (fmt, lint, type, test, coverage)
    cmds:
      - task: fmt
      - task: lint
      - task: type
      - task: test
      - task: test:coverage

  build:
    desc: Build distribution
    cmds:
      - python -m build

  clean:
    desc: Clean build artifacts
    cmds:
      - rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/ .coverage
      - find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

---

## End of Specification

**Document Version**: 1.0
**Last Updated**: 2026-01-03
**Next Review**: After Phase 1 completion

---

**Note to Coding Agents**: This specification is designed to enable parallel work. Each phase, subphase, and task clearly indicates dependencies. Tasks marked "can run in parallel" can be assigned to different agents simultaneously. Use feature branches for parallel development and merge to main after tests pass.
