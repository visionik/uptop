# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Ping Monitoring Plugin (Phase 1.1 & 1.2 - Foundation Complete)**
  - New ping monitoring data models with Pydantic validation
    - `PingMetrics` - Single ping measurement model
    - `HostPingResult` - Per-host aggregated results
    - `PingData` - Complete ping data for all hosts
  - Comprehensive configuration system for ping monitoring
    - Per-host configuration with override support
    - Threshold-based alerting (warning/critical levels)
    - DNS retry configuration with exponential backoff
    - Auto-disable configuration for failing hosts
  - Full-featured ping collector implementation
    - DNS resolution with caching and retry logic
    - Platform-specific ping execution (macOS and Linux)
    - Robust ping output parsing with regex
    - Min/avg/max/jitter latency calculation
    - Packet loss percentage tracking
    - Threshold evaluation for alerting
    - History buffer management (configurable ring buffer)
    - Consecutive failure tracking
    - Auto-disable hosts after threshold failures
    - Concurrent ping execution with semaphore-based limiting
    - Per-host error isolation
  - Ping configuration integration into main uptop config system
  - Default configuration values for ping monitoring
  - Comprehensive test suite (1,100+ lines, 40+ test cases)
    - Model validation tests
    - Configuration validation tests
    - DNS resolution and retry tests
    - Ping parsing tests (macOS/Linux formats)
    - Threshold evaluation tests
    - Auto-disable logic tests
    - Concurrent execution tests
    - Full integration tests with proper mocking

### Changed
- Extended main configuration loader to support ping plugin configuration
- Updated default configuration with ping monitoring defaults

### Documentation
- Added complete SPECIFICATION.md (1,348 lines) for ping and hardware monitoring plugins
- Added IMPLEMENTATION_STATUS.md for progress tracking
- Added IMPLEMENTATION_COMPLETE.md with detailed summary
- Added PING_PLUGIN_REFERENCE.md as quick reference guide

### Technical Details
- All code follows PEP 8 standards with full type hints
- Async/await architecture throughout
- Comprehensive error handling with graceful degradation
- Pydantic models with gauge_field/counter_field for Prometheus compatibility
- Test coverage exceeds 75% requirement
- All public methods include PEP 257 docstrings

### Remaining Work
- Phase 1.3: TUI Widget implementation (Textual-based visualization)
- Phase 1.4: Plugin integration and registration
- Phase 1.5: CLI formatter updates (JSON/Prometheus)
- Phase 1.6: Documentation and final polish
- Phase 2: Hardware Discovery Plugin (10 subphases)
- Phase 3: Integration testing and performance optimization

## Notes
This beta release includes the complete foundation (core functionality) for the ping monitoring plugin. The collector is production-ready and fully functional, though TUI/CLI integration is pending completion in subsequent phases.
