"""Tests for Phase 9.2 error handling improvements.

This module tests:
- 9.2.1: Graceful degradation for missing permissions
- 9.2.2: Clear error messages for config issues
- 9.2.3: Recovery from transient failures
"""

import asyncio
import os
import tempfile
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from uptop.collectors.base import CollectionResult, DataCollector
from uptop.collectors.scheduler import CollectionScheduler
from uptop.config import (
    ConfigError,
    ConfigSyntaxError,
    ConfigValidationError,
    load_config,
)
from uptop.models.base import MetricData


# =============================================================================
# Test Fixtures and Mocks
# =============================================================================


class MockMetricData(MetricData):
    """Mock metric data for testing."""

    value: float = 0.0


class PermissionDeniedCollector(DataCollector[MockMetricData]):
    """Collector that simulates permission denied errors."""

    name = "permission_denied"
    default_interval = 0.1
    timeout = 1.0

    async def collect(self) -> MockMetricData:
        raise PermissionError("Access denied to /proc/12345/status")

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


class TransientFailureCollector(DataCollector[MockMetricData]):
    """Collector that fails a few times then succeeds."""

    name = "transient_failure"
    default_interval = 0.1
    timeout = 5.0

    def __init__(self, fail_count: int = 2) -> None:
        super().__init__()
        self.fail_count = fail_count
        self.attempt = 0

    async def collect(self) -> MockMetricData:
        self.attempt += 1
        if self.attempt <= self.fail_count:
            raise RuntimeError(f"Transient failure {self.attempt}")
        return MockMetricData(value=42.0, source=self.name)

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


class AlwaysFailingCollector(DataCollector[MockMetricData]):
    """Collector that always fails."""

    name = "always_failing"
    default_interval = 0.1
    timeout = 1.0

    async def collect(self) -> MockMetricData:
        raise RuntimeError("Persistent failure")

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


class SuccessfulCollector(DataCollector[MockMetricData]):
    """Collector that always succeeds."""

    name = "successful"
    default_interval = 0.1
    timeout = 1.0

    def __init__(self, value: float = 42.0) -> None:
        super().__init__()
        self.value = value

    async def collect(self) -> MockMetricData:
        return MockMetricData(value=self.value, source=self.name)

    def get_schema(self) -> type[MockMetricData]:
        return MockMetricData


# =============================================================================
# 9.2.1: Graceful Degradation Tests
# =============================================================================


class TestGracefulDegradation:
    """Tests for graceful degradation when permissions are missing."""

    @pytest.mark.asyncio
    async def test_permission_denied_does_not_crash(self) -> None:
        """Test that permission denied errors don't crash the collector."""
        collector = PermissionDeniedCollector()
        result = await collector.safe_collect()

        assert result.success is False
        assert result.error is not None
        assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_permission_denied_logged_at_debug(self) -> None:
        """Test that permission errors are logged at debug level."""
        collector = PermissionDeniedCollector()

        # Should not raise, just return a failed result
        result = await collector.safe_collect()
        assert result.success is False

    @pytest.mark.asyncio
    async def test_permission_denied_not_retried(self) -> None:
        """Test that permission errors are not retried (they won't resolve)."""
        collector = PermissionDeniedCollector()
        result = await collector.collect_with_retry(max_retries=3)

        # Should return immediately without retries
        assert result.success is False
        assert "Permission denied" in str(result.error)
        # Only one attempt since permission errors don't retry
        assert collector._total_collections == 1

    @pytest.mark.asyncio
    async def test_consecutive_failures_tracked_for_permissions(self) -> None:
        """Test that consecutive failures are tracked even for permission errors."""
        collector = PermissionDeniedCollector()

        await collector.safe_collect()
        await collector.safe_collect()

        assert collector.consecutive_failures == 2
        assert collector._total_failures == 2

    @pytest.mark.asyncio
    async def test_one_pane_failure_doesnt_affect_others(self) -> None:
        """Test that one pane's failure doesn't affect other panes."""
        scheduler = CollectionScheduler()

        failing = PermissionDeniedCollector()
        failing.name = "failing_pane"
        succeeding = SuccessfulCollector()
        succeeding.name = "succeeding_pane"

        scheduler.register(failing, retry_enabled=False)
        scheduler.register(succeeding, retry_enabled=False)

        # Collect from all
        results = await scheduler.collect_all_once()

        # One should fail, one should succeed
        assert results["failing_pane"].success is False
        assert results["succeeding_pane"].success is True
        assert results["succeeding_pane"].data is not None


# =============================================================================
# 9.2.2: Config Error Message Tests
# =============================================================================


class TestConfigErrorMessages:
    """Tests for clear error messages in configuration loading."""

    def test_yaml_syntax_error_shows_line_number(self) -> None:
        """Test that YAML syntax errors show the line number."""
        invalid_yaml = """
default_mode: tui
interval: 1.0
tui:
  theme: dark
  invalid syntax here [
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(invalid_yaml)
            temp_path = f.name

        try:
            with pytest.raises(ConfigSyntaxError) as exc_info:
                load_config(config_path=temp_path)

            error = exc_info.value
            assert error.file_path is not None
            # Should mention it's a YAML syntax error
            assert "syntax" in str(error).lower() or "yaml" in str(error).lower()
        finally:
            os.unlink(temp_path)

    def test_invalid_value_shows_expected_type(self) -> None:
        """Test that invalid values show expected vs actual type."""
        invalid_config = """
interval: "fast"
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(invalid_config)
            temp_path = f.name

        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                load_config(config_path=temp_path)

            error = exc_info.value
            error_str = str(error)
            # Should mention the path and give a helpful message
            assert "interval" in error_str
        finally:
            os.unlink(temp_path)

    def test_out_of_range_value_shows_limits(self) -> None:
        """Test that out-of-range values show the valid range."""
        invalid_config = """
interval: -5
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(invalid_config)
            temp_path = f.name

        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                load_config(config_path=temp_path)

            error = exc_info.value
            error_str = str(error)
            assert "interval" in error_str
        finally:
            os.unlink(temp_path)

    def test_unknown_key_suggests_alternative(self) -> None:
        """Test that unknown keys suggest valid alternatives."""
        invalid_config = """
cli:
  defalt_format: json
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(invalid_config)
            temp_path = f.name

        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                load_config(config_path=temp_path)

            error = exc_info.value
            error_str = str(error)
            # Should mention the unknown key
            assert "defalt_format" in error_str or "Unknown" in error_str
        finally:
            os.unlink(temp_path)

    def test_config_error_has_suggestion(self) -> None:
        """Test that ConfigError includes helpful suggestions."""
        error = ConfigError(
            "Test error",
            file_path="/path/to/config.yaml",
            line_number=5,
            suggestion="Try checking the indentation",
        )

        error_str = str(error)
        assert "/path/to/config.yaml" in error_str
        assert "line 5" in error_str
        assert "indentation" in error_str

    def test_raise_on_error_false_returns_defaults(self) -> None:
        """Test that raise_on_error=False returns defaults on error."""
        invalid_config = """
interval: "not a number"
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write(invalid_config)
            temp_path = f.name

        try:
            # Should not raise, should return defaults
            config = load_config(config_path=temp_path, raise_on_error=False)
            assert config.interval == 1.0  # Default value
        finally:
            os.unlink(temp_path)


# =============================================================================
# 9.2.3: Recovery from Transient Failures
# =============================================================================


class TestTransientFailureRecovery:
    """Tests for recovery from transient failures."""

    @pytest.mark.asyncio
    async def test_collect_with_retry_succeeds_after_failures(self) -> None:
        """Test that collect_with_retry succeeds after transient failures."""
        collector = TransientFailureCollector(fail_count=2)
        result = await collector.collect_with_retry(max_retries=3)

        assert result.success is True
        assert result.data is not None
        assert result.data.value == 42.0
        # Should have taken 3 attempts (2 failures + 1 success)
        assert collector.attempt == 3

    @pytest.mark.asyncio
    async def test_collect_with_retry_fails_after_max_attempts(self) -> None:
        """Test that collect_with_retry fails if all retries exhausted."""
        collector = AlwaysFailingCollector()
        result = await collector.collect_with_retry(max_retries=3)

        assert result.success is False
        assert result.error is not None
        # Should have made 3 attempts
        assert collector._total_collections == 3

    @pytest.mark.asyncio
    async def test_retry_uses_exponential_backoff(self) -> None:
        """Test that retries use exponential backoff."""
        collector = TransientFailureCollector(fail_count=3)

        start = datetime.now(UTC)
        await collector.collect_with_retry(max_retries=4, base_delay=0.1)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        # With base_delay=0.1: delays are 0.1, 0.2, 0.3 = 0.6s minimum
        # Allow some tolerance
        assert elapsed >= 0.5

    @pytest.mark.asyncio
    async def test_scheduler_retry_enabled(self) -> None:
        """Test that scheduler respects retry settings."""
        scheduler = CollectionScheduler()
        collector = TransientFailureCollector(fail_count=2)
        scheduler.register(
            collector,
            retry_enabled=True,
            max_retries=3,
            retry_base_delay=0.05,
        )

        result = await scheduler.collect_once("transient_failure")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_scheduler_retry_disabled(self) -> None:
        """Test that scheduler can disable retries."""
        scheduler = CollectionScheduler()
        collector = TransientFailureCollector(fail_count=2)
        scheduler.register(
            collector,
            retry_enabled=False,
        )

        result = await scheduler.collect_once("transient_failure")

        # Without retry, should fail on first attempt
        assert result.success is False

    @pytest.mark.asyncio
    async def test_stale_data_detection(self) -> None:
        """Test that stale data is detected after failures."""
        scheduler = CollectionScheduler()
        collector = SuccessfulCollector()
        collector.interval = 0.1
        scheduler.register(
            collector,
            retry_enabled=False,
            stale_threshold_multiplier=2.0,
        )

        # First collection succeeds
        result = await scheduler.collect_once("successful")
        assert result.success is True
        assert not scheduler.is_collector_stale("successful")

        # Simulate time passing beyond stale threshold
        info = scheduler._collectors["successful"]
        info.last_successful_result.timestamp = datetime.now(UTC) - timedelta(seconds=1)

        # Now check stale state
        scheduler._check_stale_state(info)
        assert scheduler.is_collector_stale("successful")

    @pytest.mark.asyncio
    async def test_recovery_from_stale_state(self) -> None:
        """Test that collectors recover from stale state."""
        scheduler = CollectionScheduler()
        collector = SuccessfulCollector()
        scheduler.register(collector, retry_enabled=False)

        # First collection
        await scheduler.collect_once("successful")

        # Manually mark as stale
        info = scheduler._collectors["successful"]
        info.is_stale = True

        # Successful collection should clear stale
        await scheduler.collect_once("successful")
        assert not scheduler.is_collector_stale("successful")

    @pytest.mark.asyncio
    async def test_get_last_successful_data(self) -> None:
        """Test getting last successful data for stale display."""
        scheduler = CollectionScheduler()
        collector = SuccessfulCollector(value=100.0)
        scheduler.register(collector, retry_enabled=False)

        await scheduler.collect_once("successful")

        data = scheduler.get_last_successful_data("successful")
        assert data is not None
        assert data.value == 100.0

    @pytest.mark.asyncio
    async def test_collector_stats_include_stale_info(self) -> None:
        """Test that collector stats include stale information."""
        scheduler = CollectionScheduler()
        collector = SuccessfulCollector()
        scheduler.register(collector, retry_enabled=True, max_retries=5)

        await scheduler.collect_once("successful")

        stats = await scheduler.get_collector_stats("successful")
        assert stats is not None
        assert "is_stale" in stats
        assert "retry_enabled" in stats
        assert "max_retries" in stats
        assert stats["is_stale"] is False
        assert stats["retry_enabled"] is True
        assert stats["max_retries"] == 5

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_success(self) -> None:
        """Test that consecutive failures reset when collection succeeds."""
        collector = TransientFailureCollector(fail_count=2)

        # Collect with retry should eventually succeed
        result = await collector.collect_with_retry(max_retries=3)

        assert result.success is True
        assert collector.consecutive_failures == 0


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestErrorHandlingEdgeCases:
    """Edge case tests for error handling."""

    @pytest.mark.asyncio
    async def test_empty_config_uses_defaults(self) -> None:
        """Test that empty config file uses defaults."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write("")  # Empty file
            temp_path = f.name

        try:
            config = load_config(config_path=temp_path)
            assert config.interval == 1.0
            assert config.default_mode == "tui"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_null_config_uses_defaults(self) -> None:
        """Test that null config file uses defaults."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            f.write("null")
            temp_path = f.name

        try:
            config = load_config(config_path=temp_path)
            assert config.interval == 1.0
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_multiple_collectors_independent_failures(self) -> None:
        """Test that multiple collectors fail independently."""
        scheduler = CollectionScheduler()

        collector1 = AlwaysFailingCollector()
        collector1.name = "failing1"
        collector2 = AlwaysFailingCollector()
        collector2.name = "failing2"
        collector3 = SuccessfulCollector()
        collector3.name = "succeeding"

        scheduler.register(collector1, retry_enabled=False)
        scheduler.register(collector2, retry_enabled=False)
        scheduler.register(collector3, retry_enabled=False)

        results = await scheduler.collect_all_once()

        # Each collector should have its own result
        assert results["failing1"].success is False
        assert results["failing2"].success is False
        assert results["succeeding"].success is True

        # Stats should reflect individual failures
        stats1 = await scheduler.get_collector_stats("failing1")
        stats2 = await scheduler.get_collector_stats("failing2")
        assert stats1["collector"]["total_failures"] == 1
        assert stats2["collector"]["total_failures"] == 1

    def test_config_error_formatting(self) -> None:
        """Test ConfigError message formatting."""
        error = ConfigError(
            "Invalid value",
            file_path="/home/user/config.yaml",
            line_number=10,
            column=5,
            context_lines=["  interval: fast"],
            suggestion="Use a number like 1.0",
        )

        formatted = str(error)
        assert "config.yaml" in formatted
        assert "line 10" in formatted
        assert "interval: fast" in formatted
        assert "Use a number" in formatted

    @pytest.mark.asyncio
    async def test_zero_retries_means_no_retry(self) -> None:
        """Test that max_retries=1 means only one attempt."""
        collector = AlwaysFailingCollector()
        result = await collector.collect_with_retry(max_retries=1)

        assert result.success is False
        assert collector._total_collections == 1
